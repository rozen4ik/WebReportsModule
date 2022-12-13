import os
import fdb
import pymysql
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from sshtunnel import SSHTunnelForwarder
from configuration.models import Conf
from reports.forms import *
from reports.models import *
from reports.services.pars import Pars


class Report:
    def get_access(self, request):
        if request.user.is_authenticated:
            user = User.objects.all().select_related('profile')
            access = ""
            if request.user.profile.position_id_id == 1:
                access = "yes"
            else:
                access = "no"
            return access

    def settings_firebird(self, config):
        con = fdb.connect(
            dsn=f'{config.ip_kontur}/{config.port_kontur}:{config.path_to_db_kontur}',
            user=f'{config.user_db_kontur}',
            password=f'{config.password_db_kontur}',
            # при развертывании на хостинге положить файл "libfbclient.so.2.5.9" в папку static
            # при условии что хостинг на linux, также расскоментировать строку ниже
            # fb_library_name="static/libfbclient.so.2.5.9",
            charset="win1251"
        )
        return con

    def get_ticket(self, request):
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        page_number = request.GET.get("page")
        pars = Pars()
        page_m = ""
        ticket_form = TicketSales(request.GET)
        start_d = "01.01.01"
        end_d = "01.01.01"
        fo = ""
        data = {}

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = self.settings_firebird(config)
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

                pars.pars_ticket(trs, 'td')

                os.remove("result_scan_req.html")

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

        return data

    def get_passages_through_turnstiles(self, request):
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        page_number = request.GET.get("page")
        page_m = ""
        ticket_form = TicketSales(request.GET)
        start_d = "01.01.01"
        end_d = "01.01.01"
        fo = ""
        data = {}

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = self.settings_firebird(config)
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

        return data

    def get_rule_list(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        page_number = request.GET.get("page")
        page_m = ""
        pars = Pars()
        con = self.settings_firebird(config)
        cur = con.cursor()
        tables = cur.execute(
            "select "
            "* "
            "from "
            "HTML$RULE_LIST "
        ).fetchall()

        con.commit()
        con.close()

        st = ""
        for i in tables:
            st += f"{i[0]}"

        st = st.replace("charset=windows-1251", "charset=utf-8")
        with open('result_rule_list.html', 'w') as output_file:
            output_file.write(st)

        with open("result_rule_list.html") as fp:
            soup = BeautifulSoup(fp, "lxml")

        trs = soup.find_all('table')[1].find_all('tr')
        pars.pars_rule_list(trs)
        os.remove("result_rule_list.html")

        rule_use = RuleList.objects.all()

        page_model = Paginator(rule_use, 20)
        page_m = page_model.get_page(page_number)

        data = {
            "page_m": page_m,
            "access": access
        }

        return data

    def get_service_list(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        page_number = request.GET.get("page")
        page_m = ""
        pars = Pars()
        con = self.settings_firebird(config)
        cur = con.cursor()
        tables = cur.execute(
            "select "
            "* "
            "from "
            "HTML$SERVICE_LIST "
        ).fetchall()

        con.commit()
        con.close()

        st = ""
        for i in tables:
            st += f"{i[0]}"

        st = st.replace("charset=windows-1251", "charset=utf-8")
        with open('result_service_list.html', 'w') as output_file:
            output_file.write(st)

        with open("result_service_list.html") as fp:
            soup = BeautifulSoup(fp, "lxml")

        trs = soup.find_all('table')[1].find_all('tr')
        pars.pars_service_list(trs)
        os.remove("result_service_list.html")

        service_use = ServiceList.objects.all()

        page_model = Paginator(service_use, 20)
        page_m = page_model.get_page(page_number)

        data = {
            "page_m": page_m,
            "access": access
        }

        return data

    def get_desk_shift(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        desk = DeskItems.objects.all().delete()
        report_z_desk = ReportZDesk.objects.all().delete()
        summary_report_desk = SummaryReportDesk.objects.all().delete()
        erroneous_operations = ErroneousOperations.objects.all().delete()
        summ_money = SummMoney.objects.all().delete()
        view_pay = ViewPay.objects.all().delete()
        decoding_of_desk_sections_and_tax_groups = DecodingOfDeskSectionsAndTaxGroups.objects.all().delete()
        additional_information_about_the_desk_register = AdditionalInformationAboutTheDeskRegister\
            .objects.all().delete()
        fo = ""
        pars = Pars()
        con = self.settings_firebird(config)
        cur = con.cursor()
        desk_items = cur.execute(
            "select "
            "ID, NAME "
            "from "
            "DESK$ITEMS "
        ).fetchall()

        con.commit()
        con.close()

        for i in desk_items:
            desk = DeskItems()
            desk.id_desk = i[0]
            desk.name = i[1]
            desk.save()

        desk_form = DeskForms(request.GET)

        if desk_form.is_valid():
            filter_desk = desk_form.cleaned_data

            if filter_desk != {'desk': ''}:
                fo = "yes"
                desk = DeskItems.objects.get(name=filter_desk["desk"])
                con = self.settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML$DESK_SHIFT('{desk.id_desk}') "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                with open('result_desk_shift.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_desk_shift.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')
                pars.pars_desk_shift_1(trs, 'td')
                report_z_desk = ReportZDesk.objects.all()

                trs = soup.find_all('table')[2].find_all('tr')
                pars.pars_desk_shift_2(trs, 'td')
                summary_report_desk = SummaryReportDesk.objects.all()

                er = soup.find_all('p')

                if len(er) > 0:
                    trs = soup.find_all('table')[3].find_all('tr')
                    pars.pars_desk_shift_3(trs, 'td')
                    erroneous_operations = ErroneousOperations.objects.all()

                    trs = soup.find_all('table')[4].find_all('tr')
                    pars.pars_desk_shift_4(trs, 'td')
                    summ_money = SummMoney.objects.all()

                    trs = soup.find_all('table')[5].find_all('tr')
                    pars.pars_desk_shift_5(trs, 'td')
                    view_pay = ViewPay.objects.all()

                    trs = soup.find_all('table')[6].find_all('tr')
                    pars.pars_desk_shift_6(trs, 'td')
                    decoding_of_desk_sections_and_tax_groups = DecodingOfDeskSectionsAndTaxGroups.objects.all()

                    trs = soup.find_all('table')[7].find_all('tr')
                    pars.pars_desk_shift_7(trs, 'td')
                    additional_information_about_the_desk_register = AdditionalInformationAboutTheDeskRegister\
                        .objects.all()
                else:
                    trs = soup.find_all('table')[3].find_all('tr')
                    pars.pars_desk_shift_4(trs, 'td')
                    summ_money = SummMoney.objects.all()

                    trs = soup.find_all('table')[4].find_all('tr')
                    pars.pars_desk_shift_5(trs, 'td')
                    view_pay = ViewPay.objects.all()

                    trs = soup.find_all('table')[5].find_all('tr')
                    pars.pars_desk_shift_6(trs, 'td')
                    decoding_of_desk_sections_and_tax_groups = DecodingOfDeskSectionsAndTaxGroups.objects.all()

                    trs = soup.find_all('table')[6].find_all('tr')
                    pars.pars_desk_shift_7(trs, 'td')
                    additional_information_about_the_desk_register = AdditionalInformationAboutTheDeskRegister \
                        .objects.all()

                os.remove("result_desk_shift.html")

        data = {
            "access": access,
            "desk_form": desk_form,
            "fo": fo,
            "report_z_desk": report_z_desk,
            "summary_report_desk": summary_report_desk,
            "erroneous_operations": erroneous_operations,
            "summ_money": summ_money,
            "view_pay": view_pay,
            "decoding_of_desk_sections_and_tax_groups": decoding_of_desk_sections_and_tax_groups,
            "additional_information_about_the_desk_register": additional_information_about_the_desk_register
        }

        return data


    def get_sale_ident(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        start_d = "01.01.01"
        end_d = "01.01.01"
        page_number = request.GET.get("page")
        page_m = ""
        ident_types = IdentTypes.objects.all().delete()
        fo = ""
        pars = Pars()
        con = self.settings_firebird(config)
        cur = con.cursor()
        ident_types_list = cur.execute(
            "select "
            "ID, CAPTION "
            "from "
            "IDENT$TYPES "
        ).fetchall()

        con.commit()
        con.close()

        for i in ident_types_list:
            ident_types = IdentTypes()
            ident_types.id_ident_type = i[0]
            ident_types.caption = i[1]
            ident_types.save()

        ident_types_form = IdentTypesForms(request.GET)

        if ident_types_form.is_valid():
            filter_ident = ident_types_form.cleaned_data
            start_d = ident_types_form.cleaned_data["start_date"]
            end_d = ident_types_form.cleaned_data["end_date"]

            if filter_ident != {'ident_types': '', 'start_date': None, 'end_date': None}:
                fo = "yes"
                ident_types = IdentTypes.objects.get(caption=filter_ident["ident_types"])
                con = self.settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML$SALE_IDENT('{start_d}', '{end_d}', '{ident_types.id_ident_type}') "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                with open('result_sale_ident.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_sale_ident.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')
                pars.pars_sale_ident(trs, 'td')
                sale_ident = SaleIdent.objects.all()

                os.remove("result_sale_ident.html")

                page_model = Paginator(sale_ident, 20)
                page_m = page_model.get_page(page_number)

        data = {
            "access": access,
            "fo": fo,
            "ident_types_form": ident_types_form,
            "page_m": page_m
        }

        return data

    def get_sales_by_cat(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        start_d = "01.01.01"
        end_d = "01.01.01"
        ticket_form = TicketSales(request.GET)
        fo = ""
        pars = Pars()
        sales_by_cat = SalesByCat.objects.all()

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = self.settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML$SALES_BY_CAT('{start_d}', '{end_d}', null, null, null, null) "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                st = st.replace("charset=windows-1251", "charset=utf-8")
                with open('result_scan_sales_by_cat.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_scan_sales_by_cat.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')
                pars.pars_sales_by_cat(trs, 'td')
                sales_by_cat = SalesByCat.objects.all()

                os.remove("result_scan_sales_by_cat.html")

        data = {
            "access": access,
            "fo": fo,
            "ticket_form": ticket_form,
            "sales_by_cat": sales_by_cat
        }

        return data

    def get_sales_by_positions_stat(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        start_d = "01.01.01"
        end_d = "01.01.01"
        ticket_form = TicketSales(request.GET)
        fo = ""
        in_total = InTotal.objects.all().delete()
        pars = Pars()
        sales_by_positions_stat = SalesByPositionsStat.objects.all()

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = self.settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML$SALES_BY_POSITIONS_STAT('{start_d}', '{end_d}') "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                st = st.replace("charset=windows-1251", "charset=utf-8")
                with open('result_scan_sales_by_positions_stat.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_scan_sales_by_positions_stat.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')
                pars.pars_sales_by_positions_stat(trs, 'td')
                sales_by_positions_stat = SalesByPositionsStat.objects.all()
                sales_by_positions_stat = sales_by_positions_stat.order_by("-id")
                in_total = InTotal()
                in_total.count = sales_by_positions_stat[0].service
                in_total.summ = sales_by_positions_stat[0].position
                in_total.save()
                sales_by_positions_stat = sales_by_positions_stat[0].delete()
                sales_by_positions_stat = SalesByPositionsStat.objects.all()
                in_total = InTotal.objects.all()

                os.remove("result_scan_sales_by_positions_stat.html")

        data = {
            "access": access,
            "fo": fo,
            "ticket_form": ticket_form,
            "sales_by_positions_stat": sales_by_positions_stat,
            "in_total": in_total
        }

        return data

    def get_sales_by_sno(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        start_d = "01.01.01"
        end_d = "01.01.01"
        ticket_form = TicketSales(request.GET)
        fo = ""
        pars = Pars()
        sales_by_sno = SalesBySno.objects.all().delete()

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = self.settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML$SALES_BY_SNO('{start_d}', '{end_d}', null, null) "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                st = st.replace("charset=windows-1251", "charset=utf-8")
                with open('result_scan_sales_by_sno.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_scan_sales_by_sno.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')
                pars.pars_sales_by_sno(trs, 'td')

                os.remove("result_scan_sales_by_sno.html")

                sales_by_sno = SalesBySno.objects.all()

        data = {
            "access": access,
            "fo": fo,
            "ticket_form": ticket_form,
            "sales_by_sno": sales_by_sno
        }

        return data

    def get_ident_sales_stat(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        start_d = "01.01.01"
        end_d = "01.01.01"
        fo = ""
        pars = Pars()
        tariff_types = TariffTypes.objects.all().delete()
        ident_sales_stat = IdentSalesStat.objects.all().delete()
        con = self.settings_firebird(config)
        cur = con.cursor()

        tariff_types_list = cur.execute(
            "select "
            "ID, NAME "
            "from "
            "TARIFF$TYPES "
        ).fetchall()

        con.commit()
        con.close()

        for i in tariff_types_list:
            tariff_types = TariffTypes()
            tariff_types.id_tt = i[0]
            tariff_types.name = i[1]
            tariff_types.save()

        tariff_types_form = TariffTypesForms(request.GET)

        if tariff_types_form.is_valid():
            filter_ident = tariff_types_form.cleaned_data
            start_d = tariff_types_form.cleaned_data["start_date"]
            end_d = tariff_types_form.cleaned_data["end_date"]

            if filter_ident != {'tariff_types': '', 'start_date': None, 'end_date': None}:
                fo = "yes"
                tariff_types = TariffTypes.objects.get(name=filter_ident["tariff_types"])
                con = self.settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML$IDENT_SALES_STAT('{start_d}', '{end_d}', '{tariff_types.id_tt}') "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                with open('result_scan_ident_sales_stat.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_scan_ident_sales_stat.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')
                pars.pars_ident_sales_stat(trs, 'td')
                ident_sales_stat = IdentSalesStat.objects.all()

                os.remove("result_scan_ident_sales_stat.html")

        data = {
            "access": access,
            "fo": fo,
            "tariff_types_form": tariff_types_form,
            "ident_sales_stat": ident_sales_stat
        }

        return data

    def get_ident_sales_by_tariff(self, request):
        user = User.objects.all().select_related('profile')
        access = self.get_access(request)
        config = Conf.objects.get(id=1)
        start_d = "01.01.01"
        end_d = "01.01.01"
        ticket_form = TicketSales(request.GET)
        fo = ""
        page_number = request.GET.get("page")
        page_m = ""
        pars = Pars()
        ident_sales_by_tariff = IdentSalesByTariff.objects.all().delete()

        if ticket_form.is_valid():
            filter_ticket = ticket_form.cleaned_data
            start_d = ticket_form.cleaned_data["start_date"]
            end_d = ticket_form.cleaned_data["end_date"]

            if filter_ticket != {'start_date': None, 'end_date': None}:
                fo = "yes"
                con = self.settings_firebird(config)
                cur = con.cursor()
                tables = cur.execute(
                    "select "
                    "* "
                    "from "
                    f"HTML2$IDENT_SALES_BY_TARIFF('{start_d}', '{end_d}') "
                ).fetchall()

                con.commit()
                con.close()

                st = ""
                for i in tables:
                    st += f"{i[0]}"

                st = st.replace("charset=windows-1251", "charset=utf-8")
                with open('result_scan_ident_sales_by_tariff.html', 'w') as output_file:
                    output_file.write(st)

                with open("result_scan_ident_sales_by_tariff.html") as fp:
                    soup = BeautifulSoup(fp, "lxml")

                trs = soup.find_all('table')[1].find_all('tr')
                pars.pars_ident_sales_by_tariff(trs, 'td', start_d)

                os.remove("result_scan_ident_sales_by_tariff.html")

                ident_sales_by_tariff = IdentSalesByTariff.objects.all()
                page_model = Paginator(ident_sales_by_tariff, 18)
                page_m = page_model.get_page(page_number)

        data = {
            "access": access,
            "fo": fo,
            "ticket_form": ticket_form,
            "page_m": page_m
        }

        return data
