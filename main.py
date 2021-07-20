import requests
import datetime
import csv
import slackweb
import yaml
import logging
import logging.config
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


def main(logger):
    # 定数とか
    HP_URL = 'https://www.si.t.u-tokyo.ac.jp/'
    NORTIFY_COURSE = ['sdm', 'other']
    COURSE_COLOR = {
        'ee': '#3c6f3c',
        'sdm': '#004389',
        'psi': '#be0b3c',
        'other': '#a0a0a0'
    }

    try:
        res = requests.get(HP_URL)
    except requests.exceptions.RequestException as e:
        logger.critical('シス創HPとの接続でエラーが発生。')
        logger.critical('HTTPステータスコード:' + res.status_code)
        logger.critical(e)
        return -1
    else:
        logger.info('シス創HPからhtml取得完了')

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

        logger.debug(f'お知らせを取得。タイトル:{title}')

        if course in NORTIFY_COURSE:
            inner_notice_list.append(InnerNotice(date, link, title, course))
            logger.debug(f'お知らせのコース({course})が通知対象だったためオブジェクト化しリストに追加。')

    logger.info('学科生へのお知らせのオブジェクト化完了')

    # 過去のお知らせcsvを読み込む
    pre_inner_notice_list = []
    try:
        with open(CSV_PATH, encoding='utf_8_sig') as f:
            reader = csv.reader(f)
            logger.info('過去のお知らせcsvの読み込みに成功')
            for row in reader:
                date = str_to_date(row[0])
                link = row[1]
                title = row[2]
                course = row[3]
                pre_inner_notice_list.append(InnerNotice(date, link, title, course))
                logger.debug(f'過去のお知らせを取得。タイトル:{title}')
            logger.info('過去のお知らせのリスト化完了')
    except FileNotFoundError:
        logger.warning('csvが存在しなかったため、過去のお知らせはないものとします。')

    # 過去のお知らせと比較し、新たなお知らせを取得
    new_inner_notice_list = diff(inner_notice_list, pre_inner_notice_list)

    # 新しいお知らせをまとめてSlackで通知
    slack = slackweb.Slack(url=SLACK_URL)

    attachments = []
    for new_inner_notice in new_inner_notice_list:
        logger.debug(f'過去のお知らせとの差分から新しいお知らせを取得。タイトル:{new_inner_notice.title}')
        attachments.append({
            'color': COURSE_COLOR[new_inner_notice.course],
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
        logger.info('新しいお知らせをSlackに通知完了')
    else:
        logger.info('新しいお知らせはなかったためSlackには何も通知しません')

    # 現在のお知らせをすべてcsvに記録
    with open(CSV_PATH, 'w', encoding='utf_8_sig') as f:
        writer = csv.writer(f)
        logger.info('お知らせ記録用のcsvファイルを開くことに成功')
        for inner_notice in inner_notice_list:
            date = inner_notice.date.strftime('%Y.%m.%d')
            link = inner_notice.link
            title = inner_notice.title
            course = inner_notice.course
            writer.writerow([date, link, title, course])
            logger.debug(f'お知らせを記録。タイトル:{title}')

    logger.info('お知らせをcsvに記録完了')


def set_logging():
    with open('logging_conf.yml', 'r', encoding='utf-8') as f:
        env_data = yaml.safe_load(f)
    logconfig_dict = env_data['log_config']
    logging.config.dictConfig(logconfig_dict)


if __name__ == '__main__':
    set_logging()
    logger = logging.getLogger(__name__)

    logger.info('実行開始')
    main(logger)
    logger.info('実行完了')
