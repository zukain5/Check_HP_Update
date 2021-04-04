import requests
import datetime
import csv
import slackweb
from bs4 import BeautifulSoup
from const import CSV_PATH, SLACK_URL


class Notice:
    def __init__(self, date, link, title):
        self.date = date
        self.link = link
        self.title = title

    def __str__(self):
        return self.title

    def __eq__(self, other):
        return self.title == other.title


class InnerNotice(Notice):
    def __init__(self, date, link, title, course):
        super().__init__(date, link, title)
        self.course = course
        course_name = {
            'ee': 'E&E',
            'sdm': 'SDM',
            'psi': 'PSI',
            'other': '共通'
        }
        if self.course in course_name.keys():
            self.course_str = course_name[course]
        else:
            raise KeyError(f'Unexpected Course: {course}')


def str_to_date(date_str):
    date_list = date_str.split('.')
    year = int(date_list[0])
    month = int(date_list[1])
    day = int(date_list[2])
    return datetime.date(year, month, day)


def diff(list_a, list_b):
    list_result = []
    for elem in list_a:
        if elem not in list_b:
            list_result.append(elem)
    return list_result


def main():
    # 定数とか
    url = 'https://www.si.t.u-tokyo.ac.jp/'
    notify_course = ['sdm', 'other']

    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')

    # 学科生へのお知らせをオブジェクト化する
    inner_notices = soup.select('#notic_students_list > li > div')
    inner_notice_list = []
    for inner_notice in inner_notices:
        date_str = inner_notice.select('p.date')[0].contents[0]
        date = str_to_date(date_str)

        course = inner_notice.select('p.cat > strong')[0]['class'][0]

        elem = inner_notice.select('p.title > a')[0]
        title = elem.string
        link = elem['href']

        if course in notify_course:
            inner_notice_list.append(InnerNotice(date, link, title, course))

    # 過去のお知らせcsvを読み込む
    pre_inner_notice_list = []
    try:
        with open(CSV_PATH, encoding='utf_8_sig') as f:
            reader = csv.reader(f)
            for row in reader:
                date = str_to_date(row[0])
                link = row[1]
                title = row[2]
                course = row[3]
                pre_inner_notice_list.append(InnerNotice(date, link, title, course))
    except FileNotFoundError:
        pass

    # 過去のお知らせと比較し、新たなお知らせを取得
    new_inner_notice_list = diff(inner_notice_list, pre_inner_notice_list)

    # 新しいお知らせをまとめてSlackで通知
    slack = slackweb.Slack(url=SLACK_URL)

    attachments = []
    for new_inner_notice in new_inner_notice_list:
        course_color = {
            'ee': '#3c6f3c',
            'sdm': '#004389',
            'psi': '#be0b3c',
            'other': '#a0a0a0'
        }

        attachments.append({
            'color': course_color[new_inner_notice.course],
            'title': new_inner_notice.title,
            'title_link': new_inner_notice.link,
            'fields': [
                {
                    'title': '日付',
                    'value': new_inner_notice.date.isoformat(),
                    'short': 'true'
                },
                {
                    'title': 'コース',
                    'value': new_inner_notice.course_str,
                    'short': 'true'
                }
            ]
        })

    if new_inner_notice_list != []:
        slack.notify(text='新しいお知らせ', attachments=attachments)

    # 現在のお知らせをすべてcsvに記録
    with open(CSV_PATH, 'w', encoding='utf_8_sig') as f:
        writer = csv.writer(f)
        for inner_notice in inner_notice_list:
            date = inner_notice.date.strftime('%Y.%m.%d')
            link = inner_notice.link
            title = inner_notice.title
            course = inner_notice.course
            writer.writerow([date, link, title, course])


if __name__ == '__main__':
    main()
