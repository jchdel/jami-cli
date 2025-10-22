```bash
sudo apt-get install -y libgit2-1.9 libjsoncpp26 libsecp256k1-2 libyaml-cpp0.8 libsdbus-c++2 
wget http://builder.url/jamid
sudo mv jamid /usr/local/bin/
tmux
jamid -c -d -p
```

```bash
wget http://builder.url/{controller.py,errorsDring.py,jamictrl.py,tester.py}
sudo mv *py /usr/local/bin/
tmux
jamictrl.py -h
```
