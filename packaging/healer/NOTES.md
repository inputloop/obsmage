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

## One user, no root (systemd --user)

    install -D -m 0755 omg-heal ~/.local/lib/obsmage/omg-heal
    install -D -m 0755 omg-load-check ~/.local/lib/obsmage/omg-load-check
    install -D -m 0644 heal.conf.example ~/.config/obsmage/heal.conf     # then edit SRC and WORK
    install -D -m 0644 -t ~/.config/systemd/user user/obsmage-heal.service user/obsmage-heal.timer user/obsmage-loadcheck.service
    systemctl --user daemon-reload && systemctl --user enable --now obsmage-heal.timer
    sudo loginctl enable-linger "$USER"      # only if it should run while you are logged out

After every good run the user service starts `obsmage-loadcheck.service`: `omg-load-check` unpacks
the newest package (never installs it), starts OBS Studio under a virtual display in a throwaway HOME
with only obsmage-core added, waits for the plugin's "loaded" line, then stops OBS and everything it
started as one process group and removes the HOME. It needs `obs-studio`, `xvfb` and `xauth`;
`WORK/state/load-check` and `load.tsv` say what happened. This is the test instance on gw33.

Same healer, same follow modes; the units drop the system unit's `User=`, `StateDirectory=` and
sandbox options, which a user manager cannot use. Undo: `systemctl --user disable --now
obsmage-heal.timer` and delete the two unit files.

## Hosts without systemd (cron)

    # /etc/cron.d/obsmage-heal  (daily at 03:17, and once after boot)
    17 3 * * *  obsmage-heal  /usr/lib/obsmage/omg-heal --conf /etc/obsmage/heal.conf heal
    @reboot     obsmage-heal  sleep 600 && /usr/lib/obsmage/omg-heal --conf /etc/obsmage/heal.conf heal

The healer takes its own lock (`WORK/state/lock`), so overlapping cron runs are safe. Cron has no
hardening; run it as the dedicated unprivileged user shown, never root.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-sonnet via subagent)
