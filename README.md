# LocalDrop

Partage de fichiers d'appareil à appareil sur le même Wi-Fi, sans cloud, sans compte et sans rien installer sur l'appareil qui reçoit ou envoie. Compatible **Windows, macOS et Linux**.

<img width="757" height="583" alt="localdrop le vrai" src="https://github.com/user-attachments/assets/8f0fd693-cc3c-4a2e-9e7f-3833635fd6e5" />


## Fonctionnalités

* **Envoi rapide :** sélectionne des fichiers ou des dossiers entiers (compressés automatiquement en `.zip`).
* **Réception directe :** active la réception pour récupérer des fichiers envoyés depuis un téléphone ou un autre ordinateur directement dans ton dossier *Téléchargements*.
* **Connexion par QR code :** ouvre l'interface web sur l'autre appareil en un scan, avec glisser-déposer.
* **100 % local :** aucun fichier ne passe par Internet, tout reste sur ton Wi-Fi.

## Installation

Rendez-vous dans l'onglet **[Releases](../../releases)** et téléchargez la version adaptée à votre système :

* **Windows :** Téléchargez `LocalDrop.exe` et double-cliquez dessus. *(L'application n'étant pas signée numériquement, Windows SmartScreen peut afficher un avertissement : cliquez sur **Informations complémentaires** puis **Exécuter quand même**).*
* **macOS :** Téléchargez `LocalDrop-macos.zip`, décompressez-le, puis faites un **clic droit → Ouvrir** lors du premier lancement.
* **Linux :** Téléchargez `LocalDrop`, rendez-le exécutable (`chmod +x LocalDrop`) puis lancez-le (`./LocalDrop`).

*Alternative depuis le code source :*
```bash
pip install qrcode
python3 localdrop_app.py
