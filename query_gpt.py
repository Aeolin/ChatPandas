import ast
from io import StringIO

import openai
import re
import prompts
import pandas as pd
import numpy as np
import math as math

class ConversationContext:
    def __init__(self, id):
        self.id = id
        self.history = list()

    def add_history(self, role, message):
        self.history.append((role, message))

    def get_history(self):
        return self.history

    def to_prompt(self):
        return [{'role': role, 'content': content} for role, content in self.history]


class ChatPandas:
    def __init__(self, dataframe, open_ai_api_key):
        self.dataframe = dataframe
        openai.api_key = open_ai_api_key

    def describe(self):
        buf = StringIO()
        self.dataframe.info(buf=buf)
        return buf.getvalue()

    def init_conversation_context(self):
        context = ConversationContext(self)
        context.add_history("system", prompts.CONVERSATIONAL)


        context.add_history("system", prompts.SCHEMA.replace("<SCHEMA>", self.describe()))
        return context

    def multiline_eval(self, expr, context):
        "Evaluate several lines of input, returning the result of the last line"
        tree = ast.parse(expr)
        eval_exprs = []
        exec_exprs = []
        for module in tree.body:
            if isinstance(module, ast.Expr):
                eval_exprs.append(module.value)
            else:
                exec_exprs.append(module)
        exec_expr = ast.Module(exec_exprs, type_ignores=[])
        exec(compile(exec_expr, 'file', 'exec'), context)
        results = []
        for eval_expr in eval_exprs:
            results.append(eval(compile(ast.Expression((eval_expr)), 'file', 'eval'), context))
        return '\n'.join([str(r) for r in results])

    def ask_gpt_conversation(self, question, context=None, debug=False):
        context = context or self.init_conversation_context()
        context.add_history("user", question)
        fail_count = 0
        while True:
            response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=context.to_prompt())
            choice = response.choices[0].message
            matches = re.findall('```(.*)\n([^`]*)```', choice.content)
            if len(matches) > 0:
                context.add_history(choice.role, choice.content)
            else:
                return response.choices[0].message.content, context
                fail_count += 1
                if fail_count > 5:
                    return "Internal error, feel free to try again", context

            for role, msg in matches:
                if role.lower() == "txt":
                    return msg, context
                elif role.lower() == "python":
                    try:
                        df_copy = self.dataframe.copy()
                        if(debug):
                            print("[DEBUG]\n" + msg)

                        result = self.multiline_eval(msg, dict(pd=pd, np=np, math=math, df=df_copy))
                        if isinstance(result, pd.DataFrame):
                            result = result.to_csv()
                        context.add_history("assistant", f"data={{{str(result)}}}\n(Hint: use this to answer the question to the user)")
                    except Exception as e:
                        if debug:
                            print("[DEBUG] error: " + e.msg)
                        context.add_history("assistant", f"error={e.msg}")
                        fail_count += 1
                else:
                    if debug and msg.isspace() is False:
                        print(f"[DEBUG] unknown prefix: ({role}), " + msg)


