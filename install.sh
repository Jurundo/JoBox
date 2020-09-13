sudo python3 -m pip install -r requirements.txt
$SD=$(pwd)
cd ../
sudo mv $SD /usr/local/jobox
sudo mkdir /usr/local/lib/jobox
sudo ln -s /usr/local/jobox/jobox.py /usr/bin/jobox