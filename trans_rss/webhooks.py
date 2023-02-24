def feishu(name: str, title: str, torrent: str):
    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"开始下载 {title}",
                    "content": [
                        [
                            {
                                "tag": "text",
                                "text": f"任务: {name}"
                            }],
                        [
                            {
                                "tag": "text",
                                "text": "种子地址: "
                            },
                            {
                                "tag": "a",
                                "href": torrent,
                                "text": torrent
                            }]
                    ]
                }
            }
        }
    }
