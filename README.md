# EIC7700 kernel
This repo contains source for an EIC7700 Fedora kernel.

Patches are generated from https://github.com/jmontleon/linux-rockos

The source is generated with a command like: `export ver=6.6.78; mv linux linux-${ver}; tar --exclude-vcs -Jcvf ~/linux-${ver}.tar.xz linux-${ver}; mv linux-${ver} linux`
