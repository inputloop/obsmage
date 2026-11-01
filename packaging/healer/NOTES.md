# Installing the healer

## systemd hosts

    install -D -m 0755 omg-heal /usr/lib/obsmage/omg-heal
    install -D -m 0644 heal.conf.example /etc/obsmage/heal.conf    # then edit SRC and WORK
    install -m 0644 obsmage-heal.service obsmage-heal.timer /etc/systemd/system/
    useradd --system --home-dir /var/lib/obsmage-heal --shell /usr/sbin/nologin obsmage-heal
    systemctl daemon-reload && systemctl enable --now obsmage-heal.timer

Set `WORK=/var/lib/obsmage-heal` (the unit's `StateDirectory`). Install the build dependencies
(`dpkg-dev`, `debhelper`, `fakeroot`, a compiler toolchain, `xz-utils`, `git`, and `gnupg` for
`tagged+signed`) beforehand; the service never installs anything. Try it first with
`omg-heal --conf /etc/obsmage/heal.conf plan`, then `systemctl start obsmage-heal.service`;
`journalctl -u obsmage-heal` and `omg-heal ... status` show what happened.

## Hosts without systemd (cron)

    # /etc/cron.d/obsmage-heal  (daily at 03:17, and once after boot)
    17 3 * * *  obsmage-heal  /usr/lib/obsmage/omg-heal --conf /etc/obsmage/heal.conf heal
    @reboot     obsmage-heal  sleep 600 && /usr/lib/obsmage/omg-heal --conf /etc/obsmage/heal.conf heal

The healer takes its own lock (`WORK/state/lock`), so overlapping cron runs are safe. Cron has no
hardening; run it as the dedicated unprivileged user shown, never root.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-sonnet via subagent)
