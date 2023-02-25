python=3.10, support transmission version < 4.0

```bash
docker build . -t trans-rss:0.1.0
docker run -d --name trans-rss -v /path/to/configs:/app/configs -p out_port:80 --restart unless-stopped trans-rss:0.1.0
```

Change the config file and start this container

If your transmission is also running in docker, please add `--link <name or id>:transmission` to docker run command and use `transmission` as your transmission host in trans-rss configs.
