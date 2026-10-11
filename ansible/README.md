# Первичная настройка VPN-сервера (Ubuntu 22.04 / 24.04)

Готовит чистый VPS к установке VPN-панели в Docker (3x-ui, amnezia-wg-easy и т.п.):
пользователь с ключом, SSH на нестандартном порту, UFW с фиксом для Docker,
fail2ban, автообновления, BBR, swap.

## Что делает

| Роль       | Что настраивает |
|------------|-----------------|
| `base`     | часовой пояс, обновление пакетов, базовый софт, unattended-upgrades с автоперезагрузкой, sysctl (форвардинг, BBR, сетевая гигиена) |
| `swap`     | swap-файл: автоматически на VPS с RAM < 2 ГБ |
| `user`     | пользователь `admin_user`, SSH-ключ, sudo без пароля |
| `zsh`      | oh-my-zsh |
| `firewall` | UFW: всё входящее запрещено, SSH с rate limit, порты из `ufw_allow_rules` |
| `docker`   | Docker CE из официального репозитория, ротация логов, фикс обхода UFW |
| `fail2ban` | бан перебора SSH |
| `ssh`      | hardening sshd, смена порта на `ssh_port`, закрытие 22 |
| `panels`   | 3x-ui и/или AmneziaWG Web UI в Docker — по `vpn_panels` |

## Подготовка (один раз)

```sh
ansible-galaxy collection install -r requirements.yml
```

Нужен SSH-ключ `~/.ssh/id_ed25519` (путь меняется в `group_vars/all.yml`).

## Добавить сервер

В `inventory.yml` добавьте хост в группу `vpn` (и при необходимости в `prod`/`testing`):

```yaml
    vpn:
      hosts:
        nl_server:
          ansible_host: 203.0.113.10
```

Пользователь, порт и ключ указывать не нужно — они общие, в `group_vars/all.yml`.

## Первый запуск

На свежем сервере есть только `root` (или `ubuntu`) на порту 22:

```sh
ansible-playbook site.yml -l nl_server -k -e admin_password='пароль-для-VNC'
```

- `-k` — спросить пароль root. Если хостер положил ваш ключ в root, флаг не нужен.
- `admin_password` — пароль пользователя для входа через VNC-консоль хостера,
  если SSH сломается. По SSH вход всё равно только по ключу. Можно не задавать.
- Если хостер даёт не `root`, а `ubuntu`: `-e bootstrap_user=ubuntu`.

Плейбук сам определяет, как подключаться: если порт `ssh_port` открыт — заходит
как `admin_user` на него, иначе — как `bootstrap_user` на 22.

**Смена порта безопасна.** sshd сначала слушает 22 и `ssh_port` одновременно, плейбук
переподключается на новый порт и только после успешного входа закрывает 22. Если
хостер режет его своим firewall (security groups в панели), плейбук остановится
с ошибкой, а доступ по 22 останется — откройте порт у хостера и запустите снова.

После первого запуска:

```sh
ssh -p <ssh_port> admin@203.0.113.10
```

## Повторные запуски

```sh
ansible-playbook site.yml -l nl_server          # один сервер
ansible-playbook site.yml -l vpn                # группа
ansible-playbook site.yml -l nl_server --check --diff   # что изменится, без изменений
```

Только часть настройки — через теги: `base`, `swap`, `user`, `zsh`, `firewall`,
`docker`, `fail2ban`, `ssh`, `panels`.

```sh
ansible-playbook site.yml -l nl_server --tags firewall
```

Проверить связь: `ansible vpn -m ping` или `ansible-playbook ping.yml`.

## VPN-панель: 3x-ui или AmneziaWG

Какую панель ставить, задаётся для каждого сервера в `host_vars/<хост>/vars.yml`:

```yaml
# host_vars/de2_server/vars.yml
vpn_panels: [3x-ui]            # или [amneziawg], или [3x-ui, amneziawg]
```

Пароли храните зашифрованными в `host_vars/<хост>/vault.yml`:

```sh
ansible-vault create host_vars/de2_server/vault.yml
```
```yaml
xui_admin_password: "длинный-пароль"   # для 3x-ui
awg_ui_password: "другой-пароль"       # для amneziawg
```

Запуск (всё сразу или только панель):

```sh
ansible-playbook site.yml -l de2_server --ask-vault-pass
ansible-playbook site.yml -l de2_server --ask-vault-pass --tags panels
```

Панели ставятся в `/opt/3x-ui` и `/opt/amneziawg` (compose-файлы). Обе панели
слушают только `127.0.0.1`: снаружи недоступны, заходить через SSH-туннель.
Если убрать панель из `vpn_panels`, контейнер **не удаляется** — это делается
руками: `cd /opt/<панель> && docker compose down`.

### 3x-ui

Работает в `network_mode: host`, поэтому порты inbound-ов, созданных в панели,
открываются через `xui_open_ports`:

```yaml
xui_open_ports: ["443/tcp"]     # без /proto — tcp и udp
```

При **первой** установке плейбук задаёт логин/пароль, случайный путь панели и
`listenIP 127.0.0.1`, а в конце выводит команду туннеля и адрес:

```
ssh -N -L 2053:127.0.0.1:2053 -p <ssh_port> admin@203.0.113.10
http://localhost:2053/k3j9x0a1b2c3d4e5/
```

Путь выводится только один раз — сохраните его. При повторных запусках
настройки панели не трогаются, меняйте их в самой панели. Забыли путь:
`docker exec 3x-ui /app/x-ui setting -show`.

Встроенный fail2ban 3x-ui (лимит IP на клиента) выключен: ему нужен
`NET_ADMIN` в сети хоста. Включить: `xui_fail2ban: true`.

### AmneziaWG Web UI

Работает в bridge-сети. UDP-порты VPN перечисляются заранее — они попадают
и в `ports:` контейнера, и в UFW:

```yaml
awg_vpn_ports: [51820]
```

> ⚠️ Сервер, созданный в UI, должен слушать порт из этого списка, иначе он
> будет недоступен снаружи. Нужен ещё один сервер — добавьте порт и
> перезапустите с `--tags panels`.

UI: `ssh -N -L 8080:127.0.0.1:8080 -p <ssh_port> admin@<IP>`, затем
`http://localhost:8080`, логин `admin` / `awg_ui_password`.

### Обновление панели

Версии образов зафиксированы (`xui_image`, `awg_image`). Чтобы обновить —
поменяйте тег в `group_vars/all.yml` или `host_vars` и запустите `--tags panels`.

## Открыть порты под VPN

Порты задаются в `group_vars/all.yml` (для всех серверов) или в
`host_vars/<имя>.yml` (для одного). Способ зависит от того, как запущен контейнер.

### Контейнер с `network_mode: host` (обычно 3x-ui)

Работает как обычный сервис на хосте — список `ufw_allow_rules`:

```yaml
ufw_allow_rules:
  - { port: 443, proto: tcp, comment: "VLESS Reality" }
  - { port: 2053, proto: tcp, comment: "3x-ui panel", from: "198.51.100.7" }
```

### Контейнер с `ports:` (bridge-сеть, например amnezia-wg-easy)

Docker публикует порты в обход обычных правил UFW: без фикса `ports: "51821:51821"`
открыт всему интернету, даже если UFW его «запрещает». Фикс (роль `docker`, по
мотивам [ufw-docker](https://github.com/chaifeng/ufw-docker)) закрывает такие
порты, а разрешать их нужно через `ufw_docker_route_rules`:

```yaml
ufw_docker_route_rules:
  - { port: 51820, proto: udp, comment: "AmneziaWG" }
  - { port: 51821, proto: tcp, comment: "wg-easy UI", from: "198.51.100.7" }
```

> ⚠️ Указывается порт **внутри контейнера** — правая часть `"хост:контейнер"`.
> Для `ports: ["8443:443"]` правило будет `port: 443`.

Применить: `ansible-playbook site.yml -l nl_server --tags firewall,docker`.

Трафик из частных сетей (10/8, 172.16/12, 192.168/16) к контейнерам пропускается —
то есть VPN-клиенты видят панель.

Проверить, что закрыто, — снаружи, с другой машины:

```sh
nmap -Pn -p 22,443,51821 203.0.113.10
nmap -Pn -sU -p 51820 203.0.113.10
```

Заблокированные пакеты видны в `journalctl -k | grep 'UFW DOCKER BLOCK'`.

## Доступ к панели

Лучше вообще не открывать панель наружу: привяжите её к `127.0.0.1`
(в compose: `ports: ["127.0.0.1:2053:2053"]`, в 3x-ui — Listen IP в настройках панели)
и ходите через SSH-туннель:

```sh
ssh -N -L 2053:127.0.0.1:2053 -p <ssh_port> admin@203.0.113.10
# затем в браузере http://localhost:2053
```

Если панель нужна снаружи — хотя бы ограничьте её по IP через `from:`.

## Автоперезагрузка

unattended-upgrades ставит security-обновления в ~23:00–23:30 UTC и, если им нужна
перезагрузка (ядро, libc), перезагружает сервер в 00:00 UTC.
Без необходимости сервер не перезагружается.

Чтобы после перезагрузки поднимались контейнеры, у них должна быть restart policy:

```yaml
services:
  panel:
    restart: unless-stopped
```

Отключить: `unattended_auto_reboot: false`.

## Swap

По умолчанию `swap_size_mb: auto`: если RAM меньше 2 ГБ и у хостера нет своего swap —
создаётся `/swapfile` на 1 ГБ (`swappiness=10`). На серверах с большей памятью
ничего не делается.

Для конкретного сервера можно переопределить в `host_vars/<имя>.yml`:

```yaml
swap_size_mb: 2048   # ровно 2 ГБ; при изменении размера файл пересоздаётся
swap_size_mb: 0      # удалить /swapfile
```

## Основные переменные (`group_vars/all.yml`)

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `admin_user` | `admin` | рабочий пользователь |
| `admin_ssh_public_key_file` | `~/.ssh/id_ed25519.pub` | ключ, который кладётся на сервер |
| `admin_sudo_nopasswd` | `true` | sudo без пароля (иначе запускать с `-K`) |
| `ssh_port` | `22` | порт SSH |
| `bootstrap_user` | `root` | пользователь для первого входа |
| `timezone` | `Etc/UTC` | часовой пояс сервера |
| `base_full_upgrade` | `true` | `apt dist-upgrade` при каждом прогоне |
| `reboot_if_required` | `true` | перезагрузить в конце прогона, если нужно |
| `unattended_auto_reboot` / `_time` | `true` / `00:00` (UTC) | ночная перезагрузка |
| `swap_size_mb` | `auto` | см. «Swap» |
| `ufw_allow_rules` | `[]` | порты на хосте |
| `ufw_docker_route_rules` | `[]` | порты контейнеров |
| `fail2ban_ignoreip` | `[]` | IP, которые никогда не банить |
| `vpn_panels` | `[]` | `3x-ui`, `amneziawg` — см. «VPN-панель» |

## Если что-то пошло не так

- **Не пускает по SSH после запуска.** Зайдите через VNC-консоль хостера
  (пароль `admin_password`), проверьте `sudo sshd -t`, `sudo ufw status`,
  `systemctl status ssh`.
- **Забанил fail2ban.** С другого IP или через консоль:
  `sudo fail2ban-client set sshd unbanip <IP>`. Свой статичный IP добавьте в
  `fail2ban_ignoreip`.
- **`Host key verification failed`** после переустановки сервера — удалите
  старый ключ: `ssh-keygen -R '[203.0.113.10]:<ssh_port>'`.
- **Контейнер недоступен снаружи.** Проверьте, что порт есть в
  `ufw_docker_route_rules` (порт контейнера, а не хоста), и `sudo ufw status`.

## Ограничения

- Только Ubuntu 22.04+ на KVM. На OpenVZ/LXC-VPS не работают sysctl и часть
  функций Docker.
- IPv6-форвардинг не включается (ломает IPv6 у хостеров со SLAAC). Для VPN
  с IPv6 — включать отдельно.
- Фикс Docker ↔ UFW рассчитан на iptables-бэкенд Docker (по умолчанию).
  С экспериментальным nftables-бэкендом (Docker 29+) он не работает.
