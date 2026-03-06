user=chensong1

useradd -m -d /home/$user -s /bin/bash $user
mkdir /home/$user/.ssh
passwd -u $user

key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCplM5A4me/ZG770GBUnyF1WhJG0niE+Nqt1fnzTcuFLShe2XMMNlxJwxKDvb45O8c3Rf8aKAFAJ2epF923NkiGe69WnlrvJqKXdk3oL5dTt3HVT47MZpg2jUjS9sLjSxamEaXYv64F8HTM8EeZih0IfbMubW1YsX02yeu5MRE7QCiP4harlqGtz8Ot5IWWoQ+gfuqqZA6itbX6/0gQrHweRFfT/DrIlT+pO7ybF6/eu8gRvEz3Otoec0qT1tX802UdlGGPhpVdVtC//iG63425aLH1haG+oxxV0ugo1iwuDMtR3Vlr7spMuTrW7HrfniCFbqhEjGhTC9StJkFg/4uj chensong1"

echo "$key" >> /home/$user/.ssh/authorized_keys
chown -R $user:$user /home/$user/.ssh
chmod 700 /home/$user/.ssh
chmod 600 /home/$user/.ssh/authorized_keys
usermod -U $user
usermod -p '*' $user

