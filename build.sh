version=$(cat trans_rss/version)
docker build . -t trans-rss:$version