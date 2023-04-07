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
def check_http_website(url, auth=None):
    try:
        parsed_url = urlparse(url)
        response = requests.get(f'http://{parsed_url.netloc}', auth=auth)
        if response.status_code >= 400 and response.status_code < 500:
            return "ページが見当たらないです"
        elif response.status_code >= 500:
            return "サーバーエラー"
    except Exception as e:
        return "サイトにアクセスできません"
    return None

# SSLの有効をチェック
def check_ssl(url, auth=None):
    try:
        parsed_url = urlparse(url)
        response = requests.get(f'https://{parsed_url.netloc}', verify=True)
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
    notify_message = f"\nチェック日時: {now}\nチェックサイト数: {len(websites)}件\n"

    # Basic認証が必要な場合
    basic_auth = config.get("basic_auth")
    auth = None
    if basic_auth:
        auth = (basic_auth["username"], basic_auth["password"])

    issue_details = ""
    for url in websites:
        accessibility_error = check_http_website(url, auth)
        ssl_error = None
        issues = []

        if not accessibility_error:
            ssl_error = check_ssl(url, auth)

        issues = []

        if accessibility_error:
            issues.append(f"・{accessibility_error}")

        if ssl_error:
            issues.append(f"・{ssl_error}")

        if issues:
            issue_details += f"\n{url}\n" + "\n".join(issues) + "\n"
            issue_count += 1

    if issue_count == 0:
        notify_message += "監視中のサイトは問題ありません。"
    else:
        notify_message += f"{issue_count}件のサイトに問題がありました。\n{issue_details}"

    send_line_notify(line_token, notify_message)

    return {
        'statusCode': 200,
        'body': json.dumps('Webサイトのチェックが完了しました。')
    }
