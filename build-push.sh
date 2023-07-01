version=$(cat trans_rss/version)
podman build . -t docker.io/liyihc/trans-rss:$version -t docker.io/liyihc/trans-rss:latest
podman push docker.io/liyihc/trans-rss:$version 
podman push docker.io/liyihc/trans-rss:latest
