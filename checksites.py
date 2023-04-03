# ライブラリをインポート
import os
import json
import requests
from urllib.parse import urlparse
from datetime import datetime
import boto3
import pytz

# S3のconfig.jsonからLINEトークンと対象Webサイトを読み込む
def get_config_from_s3(bucket, key):
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket, Key=key)
    config_data = response['Body'].read().decode('utf-8')
    return json.loads(config_data)

bucket_name = 'lambda-website-checker-230323'
config_key = 'config.json'

config = get_config_from_s3(bucket_name, config_key)
line_token = config['line_token']
websites = config['websites']

# Webサイトにアクセスできるかチェック
def check_website(url):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return "サイトにアクセスできません"
    except Exception as e:
        return "サイトにアクセスできません"
    return None

# SSLの有効をチェック
def check_ssl(url):
    try:
        parsed_url = urlparse(url)
        response = requests.get(f'https://{parsed_url.netloc}', verify=True)
        if response.status_code != 200:
            return "SSL証明書が無効"
    except Exception as e:
        return "SSL証明書が無効"
    return None

# LINEへの通知設定
def send_line_notify(token, message):
    auth = {"Authorization": f"Bearer {token}"}
    content = {"message": message}
    response = requests.post(
        'https://notify-api.line.me/api/notify', headers=auth, data=content)
    return response.status_code

# AWS Lambdaが実行するメインの関数
def handler(event, context):
    # タイムゾーンを日本時間（JST）に設定
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst).strftime("%Y/%m/%d %H:%M")
    issue_count = 0
    notify_message = f"\nチェック日時: {now}\n"

    issue_details = ""
    for url in websites:
        accessibility_error = check_website(url)
        ssl_error = check_ssl(url)
        issues = []

        if ssl_error:
            issues.append(f"・{ssl_error}")

        if accessibility_error:
            issues.append(f"・{accessibility_error}")

        if issues:
            issue_details += f"{url}\n" + "\n".join(issues) + "\n\n"
            issue_count += 1

    if issue_count == 0:
        notify_message += "監視中のサイトは問題ありません。\n"
    else:
        notify_message += f"{issue_count}件のサイトに問題がありました。\n\n{issue_details}"

    send_line_notify(line_token, notify_message)

    return {
        'statusCode': 200,
        'body': json.dumps('Webサイトのチェックが完了しました。')
    }
