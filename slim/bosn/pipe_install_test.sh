#!/bin/sh
# The documented install is `curl ... | sh`: the shell's stdin is the script, yet setup
# must still prompt on the terminal. Drive it through a pty with answers typed in.
set -eu
pkill -f 'gateway run' 2>/dev/null || true
archive="$(ls -t /dist/*-linux-x64.tar.zst | head -1)"
export HOME="$(mktemp -d)" HERMES_HOME="$(mktemp -d)"
key="sk-or-v1-$(printf '0%.0s' $(seq 64))"
answers="$(mktemp)"; printf 'Ada\nLovelace\n%s\n' "$key" > "$answers"
# script(1) gives the pipeline a controlling tty; the answers arrive on it.
# One answer per prompt, after it appears: getpass drops input typed ahead of it.
(for a in Ada Lovelace "$key"; do
   n=$(grep -c "" "$answers"); i=0
   until grep -q "$(case $a in Ada) echo 'First name:' ;; Lovelace) echo 'Last name:' ;; *) echo 'API key:' ;; esac)" "$HOME/out.txt" 2>/dev/null; do
     i=$((i + 1)); [ $i -lt 600 ] || break; sleep 0.1; done
   sleep 0.5; printf '%s\n' "$a"
 done; sleep 120) | script -qec "cat /repo/slim/install.sh | sh -s -- --archive $archive -- --skip-online-checks" /dev/null \
  > "$HOME/out.txt" 2>&1 &
pid=$!
for i in $(seq 90); do grep -q "gateway healthy\|error" "$HOME/out.txt" && break; sleep 1; done
kill $pid 2>/dev/null || true
cat "$HOME/out.txt"; tail -20 "$HERMES_HOME/logs/slim-gateway.log" 2>/dev/null || true
grep -q "first_name: Ada" "$HERMES_HOME/config.yaml" 2>/dev/null || { echo "piped install did not prompt" >&2; exit 1; }
echo PIPE INSTALL OK
