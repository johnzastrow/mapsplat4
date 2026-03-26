wget https://github.com/protomaps/go-pmtiles/releases/download/v1.30.1/go-pmtiles_1.30.1_Linux_x86_64.tar.gz
tar xf go-pmtiles_1.30.1_Linux_x86_64.tar.gz
sudo mv pmtiles /usr/local/bin/
pmtiles --version


# Then verify from the QGIS Python Console (Plugins → Python Console) what PATH QGIS actually sees:
#
#  import os, shutil
#  print(os.environ.get("PATH"))
#  print(shutil.which("pmtiles"))
#
#  If pmtiles installs fine in the terminal but shutil.which still returns None from the QGIS console, the issue is QGIS's desktop launcher not inheriting your full shell PATH. In that case, run QGIS from the
#  terminal instead:
#
#  qgis &
#
#  That inherits your full shell PATH and shutil.which will find it.
