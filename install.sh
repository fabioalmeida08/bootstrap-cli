#!/bin/bash

# python3 -m venv .venv
# source .venv/bin/activate
# pip install --upgrade pip
# pip install -r requirements.txt
# deactivate

touch bootstrap.sh
script_dir_abs="$(cd "$script_dir" && pwd)"
cat <<EOF > bootstrap.sh
#!/bin/bash
python3 $script_dir_abs/main.py "\$@"
EOF

chmod +x bootstrap.sh
sudo mv bootstrap.sh /usr/local/bin/bootstrap
