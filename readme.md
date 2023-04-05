python=3.10

```bash
sh build.sh
# modify run.sh
sh run.sh
```

Change the config file and start this container

If your transmission is also running in docker, please add `--link <name or id>:transmission` to docker run command and use `transmission` as your transmission host in trans-rss configs. Or you need not add the command, just use `172.17.0.1` as the transmission host, which is host IP for containers in docker.
