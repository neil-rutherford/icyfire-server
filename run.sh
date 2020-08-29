python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
sudo apt install libffi-dev
sudo apt-get install python-dev libatlas-base-dev
python3 -m pip install -r requirements.txt

while true
do
python3 main.py
sleep 1
done