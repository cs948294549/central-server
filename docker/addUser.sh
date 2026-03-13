user=chensongdk

useradd -m -d /home/$user -s /bin/bash $user
mkdir /home/$user/.ssh
passwd -u $user

key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDBRKza+tgYIW+4q2Ioc1jo16qG4zaNCeABSoXnO0VV3q7vM7sweRpL44l1PhMaRuqXIOduQ0SGlnKZ3oWrtpL8pPw7ldIG9MVVVUKoYgIWwRfJ9Q2p3M3oI2kT3Cj28d/pdpwdVyqrcDUU6pEan9drQnTtYIcdELC3nyfr2cNvbEgmx6wKWtBXjEr8TXiG8ilMntcf1+KGD7kanc+1wO94l778N3JCrr9xHT8Pj5qh1YNJNJ+KvdTUC0ntG4fgY6vx2Cpr7XXJdZ3rKyV2KksYohAf/w1hXzI+Y7yTKXFCxTKNbFghMkoMQQ9qNDVst8HwVxK+Dr9TUPvQ4IXXBv9T chensongDK"

echo "$key" >> /home/$user/.ssh/authorized_keys
chown -R $user:$user /home/$user/.ssh
chmod 700 /home/$user/.ssh
chmod 600 /home/$user/.ssh/authorized_keys
usermod -U $user
usermod -p '*' $user