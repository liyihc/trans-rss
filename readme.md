# 说明

订阅、管理番剧，并在下载新番时，通过webhook（例如飞书）推送到手机和电脑，提醒赶快看番。

- 没有transmissoin服务也可以运行。此时单独起推送通知的作用。
- 现在nyaa使用时不要打开自动翻页。https://github.com/liyihc/trans-rss/issues/5#issue-1664541402
- 添加钉钉webhook机器人时，需要添加关键词“番剧”

# 使用docker运行

安装完docker后，运行命令
```bash
docker run -d -p 9855:80 -v trans-rss-config:/app/configs --restart unless-stopped liyihc/trans-rss
```
9855可换成任何你想要的端口，上面的命令可以直接运行，如果不懂docker，则也不需要任何修改，所有的配置都可在浏览器中进行。

安装完后，在浏览器打开`http://localhost:9855`即可打开主界面。

# Run from script（使用源码运行）

```bash
sh build.sh
# modify run.sh
sh run.sh
```

Change the config file and start this container

If your transmission is also running in docker, please add `--link <name or id>:transmission` to docker run command and use `transmission` as your transmission host in trans-rss configs. Or you need not add the command, just use `172.17.0.1` as the transmission host, which is host IP for containers in docker.


# road map 路线图

- 由于pywebio的机制，需要在新线程以发起http请求
  - 出错时同样发通知提醒（在设置中进行启动）
- 定制化不同订阅源的翻页机制
- 考虑加入对aria2的支持（通过aria2p）
