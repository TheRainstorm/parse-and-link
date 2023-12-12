import SparkApi
import os

# 密钥信息从讯飞星火网站控制台获取
# 添加到环境变量中
appid = os.environ.get("APPID")
api_secret = os.environ.get("API_SCERET")
api_key = os.environ.get("API_KEY")

domain = "generalv3"
Spark_url = "ws://spark-api.xf-yun.com/v3.1/chat"

text = [
    {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
    {"role": "user", "content": "Compose a poem that explains the concept of recursion in programming."}
]

SparkApi.answer =""
SparkApi.main(appid,api_key,api_secret,Spark_url,domain,text)

print(SparkApi.answer)
