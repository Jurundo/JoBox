sudo python3 -m pip install -r requirements.txt
SD=$(pwd)
cd ../
sudo mv $SD /opt/jobox
sudo mkdir /usr/local/lib/jobox
sudo ln -s /opt/jobox/jobox.py /usr/bin/jobox
