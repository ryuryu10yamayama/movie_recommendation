#box_office_mojoからデータを取得し、Titleリストの作成
# %precision % .2f
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import json
import re
import sqlite3
import urllib3
from bs4 import BeautifulSoup

http = urllib3.PoolManager()
with open("titles.txt", "w") as file:
    for num in range(1, 9):
        url = "http://www.boxofficemojo.com/alltime/world/"
        if num > 1:
            url = url + "?pagenum=" + str(num) + "&p=.htm"
            response = http.request("GET", url)
            soup = BeautifulSoup(response.data, "html.parser")
            rows = soup.select("tr")

            for index, row in enumerate(rows):
                if index < 3:
                    continue
                title = row.select_one("a")
                if title:
                    file.write(title.string)
                    file.write("\n")

#titleとあらすじを保管するデータベースを作成する

dbname = "recommend.db"
conn = sqlite3.connect(dbname)

conn.execute("drop table if exists movies")
conn.execute("create table movies(id,title,plot)")
conn.commit()
conn.close()

#omdapiからあらすじを取得してデータベースに保存する

http = urllib3.PoolManager()
with open("apikey.txt", "r") as file:
    apikey = file.read().strip()
    base_url = "http://www.omdbapi.com/?apikey="+apikey+"&plot=full&t="

    dbname = "recommend.db"
    conn = sqlite3.connect(dbname)

    id = 1
    with open("titles.txt", "r") as file:
        titles = file.read().splitlines()
        for title in titles:
            title = re.sub("\(\d+\)", "", title)
            title = title.replace(" ", "+")
            title = title.replace("&", "%26")
            url = base_url + title
            response = http.request("GET", url)
            data = json.loads(response.data)
            if "Title" not in data:
                print(url)
            else:
                t = data["Title"].replace("\'", "")
                plot = data["Plot"].replace("\'", "")
                conn.execute(
                    "insert into movies(id,title,plot) values('%d','%s','%s')" % (id, t, plot))
                id += 1
    conn.commit()
    conn.close()

#入力を受け取り映画のリコメンドを行う
class recommend_engine:
    def __init__(self, dbname, apikey):
        self.conn = sqlite3.connect(dbname)
        self.apikey = apikey

    def __delete__(self):
        self.conn.close()

    def __format_title(self, title):
        return title.replace(" ", "%20")

    def __format_plot(self, plot):
        return re.sub("\d", "", plot)

    def __fetch_plot(self, title):
        http = urllib3.PoolManager()
        base_url = "http://www.omdbapi.com/?apikey="+self.apikey+"&plot=full&t="

        url = base_url + self.__format_title(title)
        response = http.request("GET", url)
        data = json.loads(response.data)
        if "Plot" not in data:
            return None
        plot = data["Plot"].replace("\'", "")
        return plot

    def __find_most_similar(self, vecs):
        target_vec = vecs[-1]
        best_score = 0
        best_index = -1

        length = vecs.shape[0]

        for index, vec in enumerate(vecs):
            if index == length-1:
                break

            score = cosine_similarity(target_vec, vec)
            if score < 1 and score > best_score:
                best_score = score
                best_index = index

        if best_index == -1:
            raise Exception("オススメの映画が見つかりませんでした。違うタイトルを試してください。")

        return (best_index, best_score)

    def recommend(self, title):
        data = self.conn.execute("select * from movies")
        data_list = data.fetchall()

        title_plots = [(row[1], row[2])for row in data_list]
        for title_plot in title_plots:
            if title_plot[0] == title:
                title_plots.remove(title_plot)
        plot = self.__fetch_plot(title)
        if plot is None:
            raise Exception("作品データが取得できませんでした。違うタイトルを試してください。")
        title_plots.append((title, plot))

        vectorizer = TfidfVectorizer()
        vecs = vectorizer.fit_transform(
            [self.__format_plot(p[1])for p in title_plots])
        (best_index, best_score) = self.__find_most_similar(vecs)
        return title_plots[best_index]


with open("apikey.txt", "r") as file:
    engine = recommend_engine("recommend.db", file.read().strip())
    title = input("好きな映画のタイトルを英語で入力してください")

    try:
        (recommend_title, recommend_plot) = engine.recommend(title)
        print()

        print(title + "が好きなあなたへのおすすめはこちら！")
        print("Title: " + recommend_title)
        print("Plot: " + recommend_plot)
    except Exception as e:
            print(e)
