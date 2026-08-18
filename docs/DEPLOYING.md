# Deployment

**IMPORTANT: Running Director 4.0 is only supported on Linux-based systems. You may be able to get it working on other operating systems, but this is not supported and we may make changes breaking compatibility without warning.**

Each section here corresponds to a component of Director 4.0.

## Manager

### Dependencies

The manager uses Redis as the channel layer for Channels, the broker for Celery, and the cache, and Nginx to serve static files.

#### Redis

Install [Redis](https://redis.io/). Redis serves as the Django Channels channel layer, the Celery broker, and the cache. The default configuration works, but for security you should configure it to only listen on `localhost` and set a password.

#### Nginx

For [Nginx](https://nginx.org). this configuration *should* work, though it has not been tested (the current production environment uses a more complex configuration). It should be placed in `/etc/nginx/sites-available/director.conf`, and a symbolic link should be created at `/etc/nginx/sites-enabled/director.conf` pointing to this file.

```
server {
        listen       80 default_server;
        listen       [::]:80 default_server;
        server_name  <SERVER NAME>;
	# Optional; see the notes in manager/README.md
	#location /static/vendor {
        #    alias /usr/local/www/director/manager/director/serve/vendor;
        #    expires 7d;
        #}
	location /static {
            alias /usr/local/www/director/manager/director/serve;
            expires 1d;
        }
	location / {
            proxy_pass           http://127.0.0.1:9000;
            proxy_redirect       off;
            proxy_set_header     Host             $host;
            proxy_set_header     X-Real-IP        $remote_addr;
            proxy_set_header     X-Forwarded-For  $remote_addr;
            proxy_set_header     X-Forwarded-Host $host;
            proxy_set_header     X-Forwarded-Proto https;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_http_version 1.1;
        }

        error_page 403 /error/static/403.html;
        error_page 404 /error/static/404.html;
        error_page 502 /error/static/502.html;
        error_page 503 /error/static/unavailable.html;
}
```

Note that this will listen on port 80 (HTTP), so traffic will be sent unencrypted. If you wish to encrypt traffic using HTTPS, that will require additional setup beyond the scope of this document.

#### Celery and Daphne

First, you will need to create a new user, clone this GitHub repository somewhere as that user, and run `pipenv install`. You will also need to give the `www-data` user access to the repository so it can serve static files.

If you have root access to the server with `git`, `pipenv`, and `sudo` installed, all of this can be done with the following (currently untested):

```
groupadd director
useradd -g director director
usermod -a -G director www-data
mkdir /var/www/director
cd /var/www/director
chown director:director /var/www/director
chmod 750 /var/www/director
sudo -u director git clone 'https://github.com/tjcsl/director4.git'
sudo -u director pipenv install
```

After this, you will need to restart Nginx.

Now you can start Celery with `pipenv run celery -A director worker`, and Daphne with `pipenv run daphne -b 127.0.0.1 -p 9000 director.asgi:application`. Both should be run as the user you created in the previous step (if you ran the commands immediately above, this is the `director` user). You may wish to launch them using [supervisor](http://supervisord.org/) or your distribution's init system.

Note that you can run multiple Daphne workers. See [Nginx HTTP Load Balancing](https://docs.nginx.com/nginx/admin-guide/load-balancer/http-load-balancer/) for more information on how to set up Nginx to handle this.

## Shell

The shell host must be enrolled as an IPA client with SSSD's PAM and SSH responders enabled. Install `pamtester`, and create `/etc/pam.d/director-shell` with authentication and account stacks which include `pam_sss.so` (on Ubuntu, including `common-auth` and `common-account` is normally sufficient). The default shell settings invoke `/usr/bin/pamtester` for password and password-plus-OTP authentication and `/usr/bin/sss_ssh_authorizedkeys` for public-key authentication; their paths and the PAM service name can be overridden in `shell/shell/settings/secret.py`.

The manager's `/shell-server/` routes include an endpoint which trusts the shell host's successful IPA authentication. These routes must only be reachable from the shell server, as described in the architecture document.
