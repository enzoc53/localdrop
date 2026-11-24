#!/usr/bin/env python3
"""LocalDrop - partage de fichiers d'appareil à appareil sur le même Wi-Fi.

Application de bureau (interface graphique) en un seul fichier.
Aucune dépendance obligatoire. Pour afficher le QR code : pip install qrcode
"""
import json
import os
import re
import secrets
import shutil
import socket
import tempfile
import threading
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, quote, unquote, urlparse

CHUNK = 64 * 1024
MAX_UPLOAD = 4 * 1024 ** 3  # 4 Go


# ---------------------------------------------------------------- réseau
def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # aucun paquet envoyé, sert à trouver l'interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def safe_name(name):
    name = os.path.basename(name.replace("\\", "/"))
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "fichier"


def unique_path(folder, name):
    path = os.path.join(folder, name)
    base, ext = os.path.splitext(name)
    i = 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base} ({i}){ext}")
        i += 1
    return path


# ---------------------------------------------------------------- page web
PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LocalDrop</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,sans-serif;background:#0f1117;color:#e8eaf0;padding:20px}
main{max-width:560px;margin:auto}
h1{font-size:1.5rem;margin:0 0 4px}
p.sub{color:#8b91a3;margin:0 0 20px}
section{background:#181b25;border:1px solid #262a38;border-radius:14px;padding:16px;margin-bottom:16px}
h2{font-size:1rem;margin:0 0 12px}
.file{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 0;border-top:1px solid #262a38}
.file:first-of-type{border-top:0}
.file span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
small{color:#8b91a3}
a.btn,button{background:#4f7cff;color:#fff;border:0;border-radius:10px;padding:9px 14px;text-decoration:none;font-size:.95rem;cursor:pointer}
#drop{border:2px dashed #3a4060;border-radius:12px;padding:30px;text-align:center;color:#8b91a3}
#drop.over{border-color:#4f7cff;color:#fff}
.bar{height:6px;background:#262a38;border-radius:4px;margin-top:6px;overflow:hidden}
.bar div{height:100%;width:0;background:#4f7cff}
.up{margin-top:12px;font-size:.9rem}
</style></head><body><main>
<h1>LocalDrop</h1><p class="sub">Partage direct sur ton réseau Wi-Fi</p>
__FILES__
__UPLOAD__
</main>
<script>
const TOKEN="__TOKEN__";
const drop=document.getElementById('drop');
if(drop){
  const input=document.getElementById('picker');
  drop.onclick=()=>input.click();
  input.onchange=()=>[...input.files].forEach(send);
  ['dragenter','dragover'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('over')}));
  ['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('over')}));
  drop.addEventListener('drop',ev=>[...ev.dataTransfer.files].forEach(send));
}
function send(file){
  const list=document.getElementById('ups');
  const row=document.createElement('div');row.className='up';
  row.innerHTML='<div></div><div class="bar"><div></div></div>';
  row.firstChild.textContent=file.name+' - envoi...';
  list.appendChild(row);
  const bar=row.querySelector('.bar div');
  const x=new XMLHttpRequest();
  x.open('POST','/upload?token='+TOKEN);
  x.setRequestHeader('X-Filename',encodeURIComponent(file.name));
  x.upload.onprogress=e=>{if(e.lengthComputable)bar.style.width=(e.loaded/e.total*100)+'%'};
  x.onload=()=>{row.firstChild.textContent=file.name+(x.status==200?' - envoyé ✔':' - erreur ✘');if(x.status==200)bar.style.width='100%'};
  x.onerror=()=>{row.firstChild.textContent=file.name+' - erreur réseau ✘'};
  x.send(file);
}
</script></body></html>"""


def human(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ---------------------------------------------------------------- serveur
class Shared:
    def __init__(self):
        self.files = []  # liste de (nom, chemin)
        self.token = secrets.token_urlsafe(8)
        self.receive_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.receive_enabled = True
        self.on_receive = lambda name, size: None
        self.lock = threading.Lock()


def make_handler(shared):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _ok_token(self):
            q = parse_qs(urlparse(self.path).query)
            got = (q.get("token") or [""])[0]
            return secrets.compare_digest(got, shared.token)

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._ok_token():
                return self._send(403, "Accès refusé : scanne le QR code de l'application.")
            path = urlparse(self.path).path
            if path == "/":
                return self._page()
            if path.startswith("/download/"):
                return self._download(path[len("/download/"):])
            self._send(404, "Introuvable")

        def _page(self):
            with shared.lock:
                files = list(shared.files)
            if files:
                rows = "".join(
                    '<div class="file"><span>{n}<br><small>{s}</small></span>'
                    '<a class="btn" href="/download/{i}?token={t}">Télécharger</a></div>'.format(
                        n=esc(n), s=human(os.path.getsize(p)) if os.path.exists(p) else "?",
                        i=i, t=shared.token)
                    for i, (n, p) in enumerate(files))
                files_html = f"<section><h2>Fichiers à télécharger</h2>{rows}</section>"
            else:
                files_html = ""
            if shared.receive_enabled:
                upload_html = (
                    '<section><h2>Envoyer → destination</h2>'
                    '<div id="drop">Clique ou touche ici pour choisir des fichiers<br>'
                    '<small>ou glisse-les ici</small></div>'
                    '<input id="picker" type="file" multiple hidden><div id="ups"></div></section>')
            else:
                upload_html = ""
            if not files_html and not upload_html:
                files_html = "<section>Rien n'est partagé pour le moment.</section>"
            html = (PAGE.replace("__FILES__", files_html)
                    .replace("__UPLOAD__", upload_html)
                    .replace("__TOKEN__", shared.token))
            self._send(200, html)

        def _download(self, idx):
            try:
                name, path = shared.files[int(idx)]
                size = os.path.getsize(path)
                f = open(path, "rb")
            except (ValueError, IndexError, OSError):
                return self._send(404, "Fichier introuvable")
            with f:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition",
                                 "attachment; filename*=UTF-8''" + quote(name))
                self.end_headers()
                try:
                    while True:
                        block = f.read(CHUNK)
                        if not block:
                            break
                        self.wfile.write(block)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def do_POST(self):
            if not self._ok_token() or urlparse(self.path).path != "/upload":
                return self._send(403, "Accès refusé")
            if not shared.receive_enabled:
                return self._send(403, "La réception est désactivée")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, "Requête invalide")
            if length <= 0 or length > MAX_UPLOAD:
                return self._send(413, "Taille invalide")
            name = safe_name(unquote(self.headers.get("X-Filename", "fichier")))
            os.makedirs(shared.receive_dir, exist_ok=True)
            with shared.lock:
                dest = unique_path(shared.receive_dir, name)
                open(dest, "wb").close()  # réserve le nom
            remaining = length
            try:
                with open(dest, "wb") as out:
                    while remaining > 0:
                        block = self.rfile.read(min(CHUNK, remaining))
                        if not block:
                            raise ConnectionError("interrompu")
                        out.write(block)
                        remaining -= len(block)
            except (ConnectionError, OSError):
                try:
                    os.remove(dest)
                except OSError:
                    pass
                return
            shared.on_receive(os.path.basename(dest), length)
            self._send(200, json.dumps({"ok": True}), "application/json")

    return Handler


# ---------------------------------------------------------------- interface
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LocalDrop")
        self.geometry("760x560")
        self.minsize(700, 520)
        self.shared = Shared()
        self.shared.on_receive = lambda n, s: self.after(0, self._received, n, s)
        self.server = None
        self.thread = None
        self.tmpdir = tempfile.mkdtemp(prefix="localdrop_")
        self.url = ""
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # -- construction de la fenêtre
    def _build(self):
        pad = {"padx": 10, "pady": 6}
        left = ttk.LabelFrame(self, text="1. Envoyer → destination")
        left.place(relx=0, rely=0, relwidth=0.5, relheight=0.62)
        self.listbox = tk.Listbox(left, selectmode=tk.EXTENDED)
        self.listbox.pack(fill="both", expand=True, **pad)
        row = ttk.Frame(left)
        row.pack(fill="x", **pad)
        ttk.Button(row, text="+ Fichiers", command=self.add_files).pack(side="left")
        ttk.Button(row, text="+ Dossier", command=self.add_folder).pack(side="left", padx=4)
        ttk.Button(row, text="Retirer", command=self.remove_selected).pack(side="left")

        right = ttk.LabelFrame(self, text="2. Recevoir ← source")
        right.place(relx=0.5, rely=0, relwidth=0.5, relheight=0.62)
        self.recv_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Autoriser la réception de fichiers",
                        variable=self.recv_var, command=self._toggle_recv).pack(anchor="w", **pad)
        ttk.Label(right, text="Dossier de réception :").pack(anchor="w", padx=10)
        self.dir_var = tk.StringVar(value=self.shared.receive_dir)
        ttk.Entry(right, textvariable=self.dir_var, state="readonly").pack(fill="x", padx=10)
        row2 = ttk.Frame(right)
        row2.pack(fill="x", **pad)
        ttk.Button(row2, text="Changer…", command=self.choose_dir).pack(side="left")
        ttk.Button(row2, text="Ouvrir", command=self.open_dir).pack(side="left", padx=4)
        ttk.Label(right, text="Fichiers reçus :").pack(anchor="w", padx=10)
        self.log = tk.Listbox(right, height=5)
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        bottom = ttk.LabelFrame(self, text="3. Connexion")
        bottom.place(relx=0, rely=0.62, relwidth=1, relheight=0.38)
        self.qr_canvas = tk.Canvas(bottom, width=170, height=170, bg="white", highlightthickness=0)
        self.qr_canvas.pack(side="left", padx=12, pady=8)
        info = ttk.Frame(bottom)
        info.pack(side="left", fill="both", expand=True, padx=6)
        self.btn = ttk.Button(info, text="▶  Démarrer le partage", command=self.toggle_server)
        self.btn.pack(anchor="w", pady=(10, 6))
        self.status = ttk.Label(info, text="Arrêté. Ajoute des fichiers puis démarre.",
                                wraplength=420, justify="left")
        self.status.pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(info, textvariable=self.url_var, state="readonly").pack(fill="x", pady=6)
        row3 = ttk.Frame(info)
        row3.pack(anchor="w")
        ttk.Button(row3, text="Copier le lien", command=self.copy_url).pack(side="left")
        ttk.Label(info, text="Les deux appareils doivent être sur le même Wi-Fi.",
                  foreground="#666").pack(anchor="w", pady=(8, 0))

    # -- fichiers
    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for name, path in self.shared.files:
            self.listbox.insert(tk.END, f"{name}  ({human(os.path.getsize(path))})")

    def add_files(self):
        for p in filedialog.askopenfilenames(title="Choisir des fichiers"):
            self.shared.files.append((os.path.basename(p), p))
        self._refresh_list()

    def add_folder(self):
        d = filedialog.askdirectory(title="Choisir un dossier (il sera zippé)")
        if not d:
            return
        self.status.config(text="Compression du dossier…")
        self.update_idletasks()
        base = os.path.join(self.tmpdir, os.path.basename(d.rstrip("/\\")) or "dossier")
        zpath = shutil.make_archive(base, "zip", d)
        self.shared.files.append((os.path.basename(zpath), zpath))
        self._refresh_list()
        self.status.config(text="Dossier ajouté.")

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            del self.shared.files[i]
        self._refresh_list()

    # -- réception
    def _toggle_recv(self):
        self.shared.receive_enabled = self.recv_var.get()

    def choose_dir(self):
        d = filedialog.askdirectory(title="Dossier de réception", initialdir=self.shared.receive_dir)
        if d:
            self.shared.receive_dir = d
            self.dir_var.set(d)

    def open_dir(self):
        os.makedirs(self.shared.receive_dir, exist_ok=True)
        try:
            os.startfile(self.shared.receive_dir)  # Windows
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", self.shared.receive_dir])

    def _received(self, name, size):
        self.log.insert(0, f"✔ {name} ({human(size)})")

    # -- serveur
    def toggle_server(self):
        if self.server:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        handler = make_handler(self.shared)
        server = None
        for port in range(8765, 8800):
            try:
                server = ThreadingHTTPServer(("0.0.0.0", port), handler)
                break
            except OSError:
                continue
        if not server:
            messagebox.showerror("LocalDrop", "Aucun port libre trouvé.")
            return
        self.shared.token = secrets.token_urlsafe(8)
        self.server = server
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://{local_ip()}:{server.server_address[1]}/?token={self.shared.token}"
        self.url_var.set(self.url)
        self.status.config(text="Partage actif. Scanne le QR code avec l'autre appareil "
                                "(ou ouvre le lien dans son navigateur).")
        self.btn.config(text="■  Arrêter le partage")
        self._draw_qr(self.url)

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.url_var.set("")
        self.qr_canvas.delete("all")
        self.status.config(text="Arrêté.")
        self.btn.config(text="▶  Démarrer le partage")

    def copy_url(self):
        if self.url:
            self.clipboard_clear()
            self.clipboard_append(self.url)
            self.status.config(text="Lien copié.")

    def _draw_qr(self, text):
        c = self.qr_canvas
        c.delete("all")
        try:
            import qrcode
            qr = qrcode.QRCode(border=2)
            qr.add_data(text)
            qr.make(fit=True)
            m = qr.get_matrix()
        except ImportError:
            c.create_text(85, 85, width=150, justify="center", fill="black",
                          text="QR code indisponible.\nInstalle-le avec :\npip install qrcode\n\n"
                               "En attendant, utilise le lien.")
            return
        n = len(m)
        cell = 170 // n
        off = (170 - cell * n) // 2
        for y, line in enumerate(m):
            for x, v in enumerate(line):
                if v:
                    c.create_rectangle(off + x * cell, off + y * cell,
                                       off + (x + 1) * cell, off + (y + 1) * cell,
                                       fill="black", outline="black")

    def _quit(self):
        self.stop_server()
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
