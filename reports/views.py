import datetime
import fdb
import pymysql
import xlwt
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from sshtunnel import SSHTunnelForwarder
from bs4 import BeautifulSoup
from configuration.models import Conf
from reports.forms import TicketSales
from reports.models import Kontur, Baloon, PassagesTurnstile
from reports.services.report_xls import ReportXLS


def index(request):
    if request.user.is_authenticated:
        access = get_access(request)
        data = {
            "access": access
        }
    else:
        data = {}
    return render(request, "reports/index.html", data)


def ticket_sales(request):
    if request.user.is_authenticated:
        access = get_access(request)
        config = Conf.objects.get(id=1)
        page_number = request.GET.get("page")
        page_m = ""
        ticket_form = TicketSales(request.GET)
        start_d = "01.01.01"
        end_d = "01.01.01"
        fo = ""

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML2$ARN_SALE_STATS('{start_d}', '{end_d}') "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                st = st.replace("charset=windows-1251", "charset=utf-8")
                with open('result_scan_req.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_scan_req.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')

                pars_table(trs, 'td')

                with SSHTunnelForwarder(
                        (f'{config.ip_ssh}', 22),
                        ssh_password=f"{config.password_ssh}",
                        ssh_username=f"{config.user_ssh}",
                        remote_bind_address=('127.0.0.1', 3306)) as server:
                    con = None

                    con = pymysql.connect(
                        user=f'{config.user_db_baloon}',
                        passwd=f'{config.password_db_baloon}',
                        db='baloon',
                        host='127.0.0.1',
                        port=server.local_bind_port
                    )

                    cur = con.cursor()

                    cur.execute(
                        "SELECT "
                        "DateArc, code, permanent_rulename "
                        "FROM "
                        "Identifier "
                        f"WHERE DateArc >= '{start_d}' and DateArc <= '{end_d}'"
                    )

                    result = cur.fetchall()
                    con.close()

                    baloon = Baloon.objects.all().delete()

                    for i in result:
                        baloon = Baloon()
                        dt = i[0].strftime("%d.%m.%Y %H:%M")
                        baloon.date_bill = dt
                        baloon.id_ticket = i[1]
                        baloon.tariff = f"{i[2]} [C]"
                        baloon.save()

                    baloon = Baloon.objects.all().order_by("date_bill")
                    kontur = Kontur.objects.all().order_by("date_bill")

                    for b in baloon:
                        filt = kontur.filter(id_ticket=b.id_ticket)
                        if not filt:
                            kor = Kontur()
                            kor.date_bill = b.date_bill
                            kor.id_ticket = b.id_ticket
                            kor.tariff = b.tariff
                            kor.ticket_validity_date = ""
                            kor.date_of_ticket_passage = ""
                            kor.save()
                        else:
                            continue

            kontur = Kontur.objects.all().order_by("date_bill")
            page_model = Paginator(kontur, 20)
            page_m = page_model.get_page(page_number)

            data = {
                "ticket_form": ticket_form,
                "fo": fo,
                "page_m": page_m,
                "access": access
            }
        else:
            data = {}
        return render(request, "reports/result_ticket_sales.html", data)


def passages_through_turnstiles(request):
    if request.user.is_authenticated:
        access = get_access(request)
        config = Conf.objects.get(id=1)
        page_number = request.GET.get("page")
        page_m = ""
        ticket_form = TicketSales(request.GET)
        start_d = "01.01.01"
        end_d = "01.01.01"
        fo = ""

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "RESOLUTION_TIMESTAMP, ID_POINT, ID_TER_FROM, ID_TER_TO, IDENTIFIER_VALUE "
                    "from "
                    "IDENT$RESOLUTIONS "
                    f"where RESOLUTION_TIMESTAMP >= '{start_d}' and RESOLUTION_TIMESTAMP <= '{end_d}'"
                ).fetchall()

                passages_turnstile = PassagesTurnstile.objects.all().delete()

                for i in tables:
                    passages_turnstile = PassagesTurnstile()
                    dt = i[0].strftime("%d.%m.%Y %H:%M")
                    passages_turnstile.resolution_timestamp = dt
                    point = cur.execute(
                        "select "
                        "ID, POINT_TYPE "
                        "from "
                        "DEV$POINTS "
                        f"where ID = '{i[1]}'"
                    ).fetchall()
                    passages_turnstile.id_point = point[0][1]
                    ter_from = cur.execute(
                        "select "
                        "ID, CAPTION "
                        "from "
                        "DEV$TERRITORIES "
                        f"where ID = '{i[2]}'"
                    ).fetchall()
                    passages_turnstile.id_ter_from = ter_from[0][1]
                    ter_to = cur.execute(
                        "select "
                        "ID, CAPTION "
                        "from "
                        "DEV$TERRITORIES "
                        f"where ID = '{i[3]}'"
                    ).fetchall()
                    passages_turnstile.id_ter_to = ter_to[0][1]
                    passages_turnstile.identifier_value = i[4]
                    passages_turnstile.save()

                con.commit()
                con.close()

                passages_turnstile = PassagesTurnstile.objects.all().order_by('resolution_timestamp')
                page_model = Paginator(passages_turnstile, 20)
                page_m = page_model.get_page(page_number)

        data = {
            "access": access,
            "page_m": page_m,
            "fo": fo,
            "ticket_form": ticket_form,
        }
    else:
        data = {}
    return render(request, "reports/result_passage.html", data)


def get_access(request):
    if request.user.is_authenticated:
        user = User.objects.all().select_related('profile')
        access = ""
        if request.user.profile.position_id_id == 1:
            access = "yes"
        else:
            access = "no"
        return access


def settings_firebird(config):
    con = fdb.connect(
        dsn=f'{config.ip_kontur}/{config.port_kontur}:{config.path_to_db_kontur}',
        user=f'{config.user_db_kontur}',
        password=f'{config.password_db_kontur}',
        charset="win1251"
    )
    return con


def pars_table(trs, tag):
    count = 0
    kontur = Kontur.objects.all().delete()
    for tr in trs:
        cap = tr.find_all(tag)
        kontur = Kontur()
        for i in cap:
            caps = i.text.replace('\n', '')
            if count == 0:
                kontur.date_bill = caps
            elif count == 1:
                kontur.id_ticket = caps
            elif count == 3:
                kontur.tariff = caps
            elif count == 6:
                kontur.ticket_validity_date = caps
            elif count == 7:
                kontur.date_of_ticket_passage = caps
            count += 1
        kontur.save()
        count = 0
    kontur = Kontur.objects.all()
    kontur = kontur[0].delete()


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


def export_stat_bill(request):
    response = HttpResponse(content_type="applications/ms-excel")
    date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    response["Content-Disposition"] = "attachment; filename=StatBill " + str(date) + ".xls"

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("report")
    row_num = 0
    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    columns = [
        "Дата продажи",
        "ID билета",
        "Тариф",
        "Дата действия билета",
        "Дата прохода по билету"
    ]

    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num], font_style)

    report_xls = ReportXLS()
    kontur = report_xls.get_stat_bill(Kontur.objects.all().order_by("date_bill"))
    rows = kontur

    for row in rows:
        row_num += 1
        for col_num in range(len(row)):
            ws.write(row_num, col_num, str(row[col_num]), font_style)

    wb.save(response)

    return response


def export_passage(request):
    response = HttpResponse(content_type="applications/ms-excel")
    date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    response["Content-Disposition"] = "attachment; filename=Passage " + str(date) + ".xls"

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("report")
    row_num = 0
    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    columns = [
        "Дата прохода",
        "Устройство",
        "Откуда",
        "Куда",
        "Индификатор"
    ]

    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num], font_style)

    report_xls = ReportXLS()
    passages_turnstiles = report_xls.get_passage(PassagesTurnstile.objects.all().order_by('resolution_timestamp'))
    rows = passages_turnstiles

    for row in rows:
        row_num += 1
        for col_num in range(len(row)):
            ws.write(row_num, col_num, str(row[col_num]), font_style)

    wb.save(response)

    return response
