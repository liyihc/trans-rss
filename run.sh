version=$(cat trans_rss/version)
docker run -d --name trans-rss \
    -v /path/to/config:/app/configs \
    -p 8083:80 \
    --restart always \
    trans-rss:$version