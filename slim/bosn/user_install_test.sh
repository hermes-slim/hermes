#!/bin/sh
# Real users are not root: run the full client test as an unprivileged account.
set -eu
id hs >/dev/null 2>&1 || useradd -m -s /bin/sh hs
pkill -f 'gateway run' 2>/dev/null || true
exec setpriv --reuid hs --regid hs --init-groups env -i PATH=/usr/bin:/bin HOME=/home/hs \
  sh /repo/slim/bosn/client_install_test.sh "$@"
