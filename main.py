from query_gpt import ChatPandas
import pandas as pd

df = pd.read_csv("titanic.csv")
db = ChatPandas(dataframe=df, open_ai_api_key="")
context = None
while True:
    try:
        question = input(">>> ")
        response, context = db.ask_gpt_conversation(question, context, True)
        print(response)
    except Exception as e:
        print(e)