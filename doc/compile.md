D’abord le système de base
```
wget https://images.mobian.org/sunxi/mobian-sunxi-phosh-13.0.img.xz
xz -d mobian-sunxi-phosh-13.0.img.xz
sudo dd if=mobian-sunxi-phosh-13.0.img of=/dev/sde bs=1M
```
Ensuite, dans une console sur le pinephone, après avoir configuré le Wi-Fi,
```bash
sudo apt-get update
sudo apt-get upgrade
sudo apt-get -y install openssh-server 
sudo reboot # nouveau kernel
```
puis
```
sudo apt-get install -y build-essential git tmux
sudo apt-get install -y autoconf autoconf-archive autopoint automake cmake make dbus doxygen graphviz g++ gettext libasound2-dev libavcodec-dev libavdevice-dev libavformat-dev libboost-dev libcppunit-dev libdbus-1-dev libdbus-c++-dev libebook1.2-dev libexpat1-dev libgnutls28-dev libgtk-3-dev libjack-dev libopus-dev libpcre2-dev libpulse-dev libssl-dev libspeex-dev libspeexdsp-dev libswscale-dev libtool libudev-dev libyaml-cpp-dev sip-tester swig uuid-dev yasm libjsoncpp-dev libva-dev libvdpau-dev libpipewire-0.3-dev libmsgpack-dev pandoc nasm dpkg-dev libsystemd-dev libarchive-dev libgit2-dev libx264-dev libsecp256k1-dev libsdbus-c++-dev libsdbus-c++-bin
git clone https://git.jami.net/savoirfairelinux/jami-daemon.git
cd jami-daemon
##sed -i -e q/-j\${NPROC}/-j1/' CMakeList.txt # to avoid killing the pinephone
mkdir build
cd build
## je veux juste la voix pour commencer...
cmake .. -DJAMI_DBUS=on -DJAMI_VIDEO=off -DJAMI_VIDEO_ACCEL=off # c'est long
make # ça aussi, c'est long...
sudo make install
#Install the project...
#-- Install configuration: ""
#-- Installing: /usr/local/lib/libjami-core.a
#-- Installing: /usr/local/libexec/jamid
```
Pour tester, lancer dans un premier terminal
```
/usr/local/libexec/jamid -c -d -p 
```
et dans un autre terminal
```
~/jami-daemon/tools/jamictrl/jamictrl.py --list-audio-devices
#Output Devices
#0: default
#1: Audio interne Internal speaker
#Input Devices
#0: default
#1: Monitor of Audio interne Internal speaker
#2: Audio interne Internal Microphone
```
