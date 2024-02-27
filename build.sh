version=$(cat trans_rss/version)
docker build . -t docker.io/liyihc/trans-rss:$version -t docker.io/liyihc/trans-rss:latest
