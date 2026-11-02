"""Excel workbooks (xlsxwriter, so every formula also carries its computed value and the files read
correctly in pandas / openpyxl data_only without a spreadsheet application recalculating them)."""
from __future__ import annotations

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell as cell

import issuer as I
from common import SYNTHETIC_FOOTER, SYNTHETIC_MARK

P4 = ["H1FY27", "FY26", "FY25", "FY24"]


class Book:
    def __init__(self, path, title):
        self.wb = xlsxwriter.Workbook(str(path))
        self.wb.set_properties({"title": title, "author": "Synthetic bundle generator", "comments": SYNTHETIC_MARK})
        f = self.wb.add_format
        base = {"font_name": "Arial", "font_size": 9}
        self.f = {
            "title": f({**base, "bold": True, "font_size": 12, "font_color": "#1F3A5F"}),
            "note": f({**base, "italic": True, "font_color": "#666666"}),
            "hdr": f({**base, "bold": True, "bg_color": "#DCE3EC", "border": 1, "text_wrap": True, "valign": "top"}),
            "txt": f({**base, "border": 1, "text_wrap": True, "valign": "top"}),
            "txtb": f({**base, "border": 1, "bold": True, "text_wrap": True}),
            "num": f({**base, "border": 1, "num_format": "#,##,##0.00;(#,##,##0.00);-", "font_color": "#0000FF"}),
            "numf": f({**base, "border": 1, "num_format": "#,##,##0.00;(#,##,##0.00);-"}),
            "numb": f({**base, "border": 1, "bold": True, "num_format": "#,##,##0.00;(#,##,##0.00);-"}),
            "int": f({**base, "border": 1, "num_format": "#,##,##0;(#,##,##0);-", "font_color": "#0000FF"}),
            "intf": f({**base, "border": 1, "num_format": "#,##,##0;(#,##,##0);-"}),
            "intb": f({**base, "border": 1, "bold": True, "num_format": "#,##,##0;(#,##,##0);-"}),
            "pct": f({**base, "border": 1, "num_format": "0.00%"}),
            "pctin": f({**base, "border": 1, "num_format": "0.00%", "font_color": "#0000FF"}),
            "ratio": f({**base, "border": 1, "num_format": "0.00"}),
            "date": f({**base, "border": 1}),
        }

    def sheet(self, name, title, widths, note=None):
        ws = self.wb.add_worksheet(name)
        ws.set_landscape()
        ws.set_paper(9)
        ws.fit_to_pages(1, 0)
        ws.set_footer("&L&6" + SYNTHETIC_FOOTER + "&R&8Page &P of &N")
        ws.write(0, 0, title, self.f["title"])
        ws.write(1, 0, note or ("All amounts in ₹ lakhs unless stated. Blue = input values; black = formulas. " + SYNTHETIC_MARK), self.f["note"])
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)
        return ws

    def close(self):
        self.wb.close()


def _sum_col(ws, b, r0, r1, col, value, fmt="numb"):
    ws.write_formula(r1 + 1, col, f"=SUM({cell(r0, col)}:{cell(r1, col)})", b.f[fmt], value)


# ------------------------------------------------------------------ share capital --------------
def share_capital(d, path):
    b = Book(path, "Share capital build-up")
    ws = b.sheet("Allotments", "Equity share capital build-up since incorporation", [5, 16, 34, 22, 30, 12, 9, 10, 10, 15, 14, 16])
    hdr = ["Sr.", "Date of allotment", "Nature of allotment", "Consideration", "Allottee", "No. of shares", "Face value (₹)",
           "Issue price (₹)", "Premium (₹)", "Amount received (₹)", "Cumulative no. of shares", "Cumulative paid-up capital (₹)"]
    ws.write_row(3, 0, hdr, b.f["hdr"])
    r = 4
    cum = 0
    sr = 1
    for a in d["allotments"]:
        allot = ({k: v * I.BONUS_RATIO for k, v in d["holdings"]["pre_bonus"].items()} if a["allottees"] == "BONUS" else a["allottees"])
        for name, n in allot.items():
            cum += n
            ws.write(r, 0, sr, b.f["intf"])
            ws.write(r, 1, a["date"], b.f["txt"])
            ws.write(r, 2, a["nature"], b.f["txt"])
            ws.write(r, 3, a["consideration"], b.f["txt"])
            ws.write(r, 4, name, b.f["txt"])
            ws.write_number(r, 5, n, b.f["int"])
            ws.write_number(r, 6, 10, b.f["int"])
            ws.write_number(r, 7, a["price"], b.f["num"])
            ws.write_formula(r, 8, f"=MAX({cell(r, 7)}-{cell(r, 6)},0)", b.f["numf"], max(a["price"] - 10, 0))
            ws.write_formula(r, 9, f"={cell(r, 5)}*{cell(r, 7)}", b.f["numf"], n * a["price"])
            prev = f"{cell(r - 1, 10)}+" if r > 4 else ""
            ws.write_formula(r, 10, f"={prev}{cell(r, 5)}", b.f["intf"], cum)
            ws.write_formula(r, 11, f"={cell(r, 10)}*10", b.f["intf"], cum * 10)
            r += 1
            sr += 1
    ws.write(r, 4, "Total", b.f["txtb"])
    ws.write_formula(r, 5, f"=SUM({cell(4, 5)}:{cell(r - 1, 5)})", b.f["intb"], cum)
    ws.write_formula(r, 9, f"=SUM({cell(4, 9)}:{cell(r - 1, 9)})", b.f["numb"],
                     sum(n * a["price"] for a in d["allotments"] if a["allottees"] != "BONUS" for n in a["allottees"].values()))
    ws.write(r + 2, 0, "Note: Shares allotted on 28 March 2020 were on conversion of unsecured loans (no cash received); the "
             "amount column shows the loan converted. All shares were dematerialised by 30 September 2026 (ISIN INE0SYN01017, synthetic).", b.f["note"])

    ws = b.sheet("Shareholding", "Shareholding pattern - pre-issue (as on 30 September 2026)", [36, 20, 16, 16, 16, 12])
    ws.write_row(3, 0, ["Shareholder", "Category", "Shares before bonus", "Bonus shares (4:1)", "Shares pre-issue", "% of pre-issue capital"], b.f["hdr"])
    r = 4
    h = d["holdings"]
    for name in d["shareholders"]:
        ws.write(r, 0, name, b.f["txt"])
        ws.write(r, 1, d["sh_category"][name], b.f["txt"])
        ws.write_number(r, 2, h["pre_bonus"][name], b.f["int"])
        ws.write_formula(r, 3, f"={cell(r, 2)}*4", b.f["intf"], h["pre_bonus"][name] * 4)
        ws.write_formula(r, 4, f"={cell(r, 2)}+{cell(r, 3)}", b.f["intf"], h["pre_issue"][name])
        r += 1
    last = r - 1
    for rr in range(4, r):
        name = d["shareholders"][rr - 4]
        ws.write_formula(rr, 5, f"={cell(rr, 4)}/{cell(r, 4, True, True)}", b.f["pct"], h["pre_issue"][name] / I.SHARES_PRE_ISSUE)
    ws.write(r, 0, "Total", b.f["txtb"])
    for col, v in ((2, I.SHARES_PRE_BONUS), (3, I.SHARES_PRE_BONUS * 4), (4, I.SHARES_PRE_ISSUE)):
        ws.write_formula(r, col, f"=SUM({cell(4, col)}:{cell(last, col)})", b.f["intb"], v)
    ws.write_formula(r, 5, f"=SUM({cell(4, 5)}:{cell(last, 5)})", b.f["pct"], 1.0)
    ws.write(r + 2, 0, "Promoter and Promoter Group holding", b.f["txtb"])
    ws.write_formula(r + 2, 4, f"=SUM({cell(4, 4)}:{cell(7, 4)})", b.f["intb"], sum(h["pre_issue"][n] for n in d["shareholders"][:4]))
    ws.write_formula(r + 2, 5, f"={cell(r + 2, 4)}/{cell(r, 4)}", b.f["pct"], sum(h["pre_issue"][n] for n in d["shareholders"][:4]) / I.SHARES_PRE_ISSUE)

    ws = b.sheet("Authorised_Capital", "Changes in authorised share capital", [20, 22, 18, 50])
    ws.write_row(3, 0, ["Date of members' approval", "Authorised capital (₹)", "Number of shares", "Particulars"], b.f["hdr"])
    for i, (dt, amt, sh) in enumerate(d["authorised_capital"]):
        ws.write(4 + i, 0, dt, b.f["txt"])
        ws.write_number(4 + i, 1, amt, b.f["int"])
        ws.write_number(4 + i, 2, sh, b.f["int"])
        ws.write(4 + i, 3, "On incorporation" if i == 0 else "Increase approved by ordinary resolution", b.f["txt"])

    ws = b.sheet("Cost_of_Acquisition", "Average cost of acquisition of shares held by Promoters (bonus adjusted)", [36, 18, 20, 18])
    ws.write_row(3, 0, ["Promoter", "Shares held (pre-issue)", "Total cost of acquisition (₹)", "Average cost per share (₹)"], b.f["hdr"])
    for i, name in enumerate(("Hemant Ramniklal Desai", "Kavita Hemant Desai")):
        rr = 4 + i
        cost = sum(a["allottees"].get(name, 0) * a["price"] for a in d["allotments"] if a["allottees"] != "BONUS")
        ws.write(rr, 0, name, b.f["txt"])
        ws.write_number(rr, 1, h["pre_issue"][name], b.f["int"])
        ws.write_number(rr, 2, cost, b.f["num"])
        ws.write_formula(rr, 3, f"=ROUND({cell(rr, 2)}/{cell(rr, 1)},2)", b.f["numf"], round(cost / h["pre_issue"][name], 2))
    b.close()
    return path


# ------------------------------------------------------------------ restated workings ----------
def fin_workings(d, path):
    b = Book(path, "Restated financial statements - workings")
    cols = P4
    labels = ["30-Sep-2026", "31-Mar-2026", "31-Mar-2025", "31-Mar-2024"]
    plabels = ["H1 FY27 (6 months)", "FY 2025-26", "FY 2024-25", "FY 2023-24"]

    def write_block(ws, start, rows, period_labels):
        ws.write_row(start, 0, ["Particulars"] + period_labels, b.f["hdr"])
        pos = {}
        r = start + 1
        for key, label, vals, kind in rows:
            fmtt = b.f["txtb"] if kind in ("total", "head") else b.f["txt"]
            ws.write(r, 0, label, fmtt)
            if kind == "head":
                r += 1
                continue
            for j, v in enumerate(vals):
                if kind == "total":
                    parts = "+".join(cell(pos[k], 1 + j) if not k.startswith("-") else "-" + cell(pos[k[1:]], 1 + j) for k in key[1])
                    ws.write_formula(r, 1 + j, "=" + parts, b.f["numb"], v)
                else:
                    ws.write_number(r, 1 + j, v, b.f["num"])
            pos[key if isinstance(key, str) else key[0]] = r
            r += 1
        return pos, r

    bs = [d["bs"][I.CLOSE[p]] for p in cols]
    pl = [d["pl"][p] for p in cols]
    cf = [d["cf"][p] for p in cols]
    ws = b.sheet("Balance_Sheet", "Restated statement of assets and liabilities", [58, 16, 16, 16, 16])
    rows = [
        ("h1", "EQUITY AND LIABILITIES", [], "head"),
        ("sc", "Share capital", [x["share_capital"] for x in bs], "in"),
        ("rs", "Reserves and surplus", [x["other_equity"] for x in bs], "in"),
        (("nw", ["sc", "rs"]), "Shareholders' funds", [x["net_worth"] for x in bs], "total"),
        ("ltb", "Long-term borrowings", [x["lt_borrowings"] for x in bs], "in"),
        ("dtl", "Deferred tax liabilities (net)", [x["dtl"] for x in bs], "in"),
        ("ltp", "Long-term provisions", [x["gratuity_nc"] for x in bs], "in"),
        ("stb", "Short-term borrowings", [x["st_borrowings"] for x in bs], "in"),
        ("tp", "Trade payables", [x["payables"] for x in bs], "in"),
        ("ocl", "Other current liabilities", [x["ocl"] for x in bs], "in"),
        ("stp", "Short-term provisions", [I.r2(x["gratuity_c"] + x["tax_liab"]) for x in bs], "in"),
        (("tl", ["nw", "ltb", "dtl", "ltp", "stb", "tp", "ocl", "stp"]), "TOTAL EQUITY AND LIABILITIES", [x["total_liabilities"] for x in bs], "total"),
        ("h2", "ASSETS", [], "head"),
        ("ppe", "Property, plant and equipment (net)", [x["ppe_net"] for x in bs], "in"),
        ("cwip", "Capital work-in-progress", [x["cwip"] for x in bs], "in"),
        ("ltla", "Long-term loans and advances", [I.r2(x["cap_adv"] + x["deposits"]) for x in bs], "in"),
        ("inv", "Inventories", [x["inventories"] for x in bs], "in"),
        ("tr", "Trade receivables", [x["receivables"] for x in bs], "in"),
        ("cash", "Cash and bank balances", [x["cash_total"] for x in bs], "in"),
        ("oca", "Short-term loans and advances and other current assets", [x["oca"] for x in bs], "in"),
        (("ta", ["ppe", "cwip", "ltla", "inv", "tr", "cash", "oca"]), "TOTAL ASSETS", [x["total_assets"] for x in bs], "total"),
    ]
    bpos, r = write_block(ws, 3, rows, labels)
    ws.write(r + 1, 0, "Check: total assets less total equity and liabilities (should be zero)", b.f["note"])
    for j in range(4):
        ws.write_formula(r + 1, 1 + j, f"=ROUND({cell(bpos['ta'], 1 + j)}-{cell(bpos['tl'], 1 + j)},2)", b.f["numf"], 0)

    ws = b.sheet("Profit_and_Loss", "Restated statement of profit and loss", [58, 16, 16, 16, 16])
    rows = [
        ("rev", "Revenue from operations", [x["revenue"] for x in pl], "in"),
        ("oi", "Other income", [x["oi"] for x in pl], "in"),
        (("ti", ["rev", "oi"]), "Total income", [I.r2(x["revenue"] + x["oi"]) for x in pl], "total"),
        ("comc", "Cost of materials consumed", [x["comc"] for x in pl], "in"),
        ("chg", "Changes in inventories of FG and WIP", [x["inv_change"] for x in pl], "in"),
        ("emp", "Employee benefits expense", [x["emp"] for x in pl], "in"),
        ("fin", "Finance costs", [x["fin"] for x in pl], "in"),
        ("dep", "Depreciation and amortisation", [x["dep"] for x in pl], "in"),
        ("oe", "Other expenses", [x["oe"] for x in pl], "in"),
        (("te", ["comc", "chg", "emp", "fin", "dep", "oe"]), "Total expenses", [I.r2(x["comc"] + x["inv_change"] + x["emp"] + x["fin"] + x["dep"] + x["oe"]) for x in pl], "total"),
        (("pbt", ["ti", "-te"]), "Profit before tax", [x["pbt"] for x in pl], "total"),
        ("ct", "Current tax", [x["tax_current"] for x in pl], "in"),
        ("dt", "Deferred tax", [x["tax_deferred"] for x in pl], "in"),
        (("pat", ["pbt", "-ct", "-dt"]), "Profit after tax", [x["pat"] for x in pl], "total"),
        (("ebitda", ["pbt", "fin", "dep", "-oi"]), "EBITDA (PBT + finance costs + depreciation - other income)", [x["ebitda"] for x in pl], "total"),
    ]
    ppos, r = write_block(ws, 3, rows, plabels)

    ws = b.sheet("Cash_Flow", "Restated statement of cash flows (summary)", [58, 16, 16, 16, 16])
    rows = [
        ("cfo", "Net cash from operating activities", [x["cfo"] for x in cf], "in"),
        ("cfi", "Net cash used in investing activities", [x["cfi"] for x in cf], "in"),
        ("cff", "Net cash from / (used in) financing activities", [x["cff"] for x in cf], "in"),
        (("net", ["cfo", "cfi", "cff"]), "Net change in cash and cash equivalents", [x["net_change"] for x in cf], "total"),
        ("op", "Opening cash and cash equivalents", [x["cash_open"] for x in cf], "in"),
        (("cl", ["net", "op"]), "Closing cash and cash equivalents", [x["cash_close"] for x in cf], "total"),
    ]
    write_block(ws, 3, rows, plabels)

    ws = b.sheet("Ratios", "Key ratios (formulas linked to the statements)", [58, 16, 16, 16, 16],
                 note="H1 FY27 ratios are not annualised. EPS and NAV per share use 1,00,00,000 bonus-adjusted shares.")
    ws.write_row(3, 0, ["Ratio"] + plabels, b.f["hdr"])
    R = d["ratios"]
    defs = [("EBITDA margin", lambda j: f"=Profit_and_Loss!{cell(ppos['ebitda'], 1 + j)}/Profit_and_Loss!{cell(ppos['rev'], 1 + j)}",
             lambda p: R[p]["ebitda_margin_pct"] / 100, "pct"),
            ("PAT margin", lambda j: f"=Profit_and_Loss!{cell(ppos['pat'], 1 + j)}/Profit_and_Loss!{cell(ppos['rev'], 1 + j)}",
             lambda p: R[p]["net_profit_pct"] / 100, "pct"),
            ("Return on net worth (closing)", lambda j: f"=Profit_and_Loss!{cell(ppos['pat'], 1 + j)}/Balance_Sheet!{cell(bpos['nw'], 1 + j)}",
             lambda p: R[p]["ronw_pct"] / 100, "pct"),
            ("Debt-equity (times)", lambda j: f"=(Balance_Sheet!{cell(bpos['ltb'], 1 + j)}+Balance_Sheet!{cell(bpos['stb'], 1 + j)})/Balance_Sheet!{cell(bpos['nw'], 1 + j)}",
             lambda p: R[p]["debt_equity"], "ratio"),
            ("EPS - basic and diluted (₹)", lambda j: f"=ROUND(Profit_and_Loss!{cell(ppos['pat'], 1 + j)}*100000/10000000,2)",
             lambda p: R[p]["eps"], "ratio"),
            ("NAV per share (₹)", lambda j: f"=ROUND(Balance_Sheet!{cell(bpos['nw'], 1 + j)}*100000/10000000,2)",
             lambda p: R[p]["nav_per_share"], "ratio")]
    for i, (lab, fml, val, fmt) in enumerate(defs):
        ws.write(4 + i, 0, lab, b.f["txt"])
        for j, p in enumerate(cols):
            v = val(p)
            if lab.startswith("Debt"):
                v = (d["bs"][I.CLOSE[p]]["lt_borrowings"] + d["bs"][I.CLOSE[p]]["st_borrowings"]) / d["bs"][I.CLOSE[p]]["net_worth"]
            if lab.startswith("EBITDA"):
                v = d["pl"][p]["ebitda"] / d["pl"][p]["revenue"]
            if lab.startswith("PAT"):
                v = d["pl"][p]["pat"] / d["pl"][p]["revenue"]
            if lab.startswith("Return"):
                v = d["pl"][p]["pat"] / d["bs"][I.CLOSE[p]]["net_worth"]
            ws.write_formula(4 + i, 1 + j, fml(j), b.f[fmt], v)
    b.close()
    return path


# ------------------------------------------------------------------ operations -----------------
def operational(d, path):
    o, pl = d["ops"], d["pl"]
    b = Book(path, "Operational data")
    labs = ["H1 FY27", "FY 2025-26", "FY 2024-25", "FY 2023-24"]
    ws = b.sheet("Capacity", "Installed capacity, production and utilisation", [46, 14, 14, 14, 14],
                 note="Certified by chartered engineer Er. Bhavin S. Mehta on 19 October 2026. H1 capacity is for six months.")
    ws.write_row(3, 0, ["Particulars"] + labs, b.f["hdr"])
    items = [("Installed lamination capacity (MT)", "capacity_mtpa"), ("Production - laminated output (MT)", "production_mt")]
    for i, (lab, k) in enumerate(items):
        ws.write(4 + i, 0, lab, b.f["txt"])
        for j, p in enumerate(P4):
            ws.write_number(4 + i, 1 + j, o[k][p], b.f["int"])
    ws.write(6, 0, "Capacity utilisation - lamination", b.f["txt"])
    for j, p in enumerate(P4):
        ws.write_formula(6, 1 + j, f"={cell(5, 1 + j)}/{cell(4, 1 + j)}", b.f["pct"], o["production_mt"][p] / o["capacity_mtpa"][p])
    for i, (lab, k) in enumerate([("Installed pouch capacity (million pcs)", "pouch_capacity_mn"), ("Pouch production (million pcs)", "pouch_production_mn")]):
        ws.write(7 + i, 0, lab, b.f["txt"])
        for j, p in enumerate(P4):
            ws.write_number(7 + i, 1 + j, o[k][p], b.f["int"])
    ws.write(9, 0, "Capacity utilisation - pouches", b.f["txt"])
    for j, p in enumerate(P4):
        ws.write_formula(9, 1 + j, f"={cell(8, 1 + j)}/{cell(7, 1 + j)}", b.f["pct"], o["pouch_production_mn"][p] / o["pouch_capacity_mn"][p])
    ws.write(10, 0, "Revenue per MT of laminated output (₹ per kg)", b.f["txt"])
    for j, p in enumerate(P4):
        ws.write_number(10, 1 + j, round(pl[p]["sale_of_products"] * 1e5 / (o["production_mt"][p] * 1000), 2), b.f["num"])

    def pct_sheet(name, title, data, base_key, base_label):
        ws = b.sheet(name, title, [46, 14, 14, 14, 14])
        ws.write_row(3, 0, ["Category (% share)"] + labs, b.f["hdr"])
        r = 4
        for k, v in data.items():
            ws.write(r, 0, k, b.f["txt"])
            for j, p in enumerate(P4):
                ws.write_number(r, 1 + j, v[p] / 100, b.f["pctin"])
            r += 1
        ws.write(r, 0, "Total", b.f["txtb"])
        for j in range(4):
            ws.write_formula(r, 1 + j, f"=SUM({cell(4, 1 + j)}:{cell(r - 1, 1 + j)})", b.f["pct"], sum(v[P4[j]] for v in data.values()) / 100)
        ws.write(r + 2, 0, base_label, b.f["txtb"])
        for j, p in enumerate(P4):
            ws.write_number(r + 2, 1 + j, pl[p][base_key], b.f["num"])
        ws.write(r + 3, 0, "Amount (₹ lakhs) by category", b.f["txtb"])
        for i, k in enumerate(data):
            ws.write(r + 4 + i, 0, k, b.f["txt"])
            for j in range(4):
                ws.write_formula(r + 4 + i, 1 + j, f"=ROUND({cell(4 + i, 1 + j)}*{cell(r + 2, 1 + j)},2)", b.f["numf"],
                                 round(data[k][P4[j]] / 100 * pl[P4[j]][base_key], 2))

    pct_sheet("Product_Mix", "Sale of products by product category", o["product_mix"], "sale_of_products", "Sale of products (₹ lakhs)")
    pct_sheet("End_Use", "Sale of products by end-use industry", o["end_use"], "sale_of_products", "Sale of products (₹ lakhs)")
    pct_sheet("Domestic_States", "Domestic sale of products by state", o["states"], "domestic", "Domestic sale of products (₹ lakhs)")

    ws = b.sheet("Customers_Suppliers", "Customer and supplier concentration", [46, 14, 14, 14, 14])
    ws.write_row(3, 0, ["Particulars"] + labs, b.f["hdr"])
    rows = [("Number of customers served", "customers", "int"), ("Top 1 customer (% of revenue)", "top1", "pct"),
            ("Top 5 customers (% of revenue)", "top5", "pct"), ("Top 10 customers (% of revenue)", "top10", "pct"),
            ("Top 10 suppliers (% of purchases)", "supplier_top10", "pct"), ("Exports (% of sale of products)", "export_share", "pct")]
    for i, (lab, k, kind) in enumerate(rows):
        ws.write(4 + i, 0, lab, b.f["txt"])
        for j, p in enumerate(P4):
            if kind == "int":
                ws.write_number(4 + i, 1 + j, o[k][p], b.f["int"])
            else:
                ws.write_number(4 + i, 1 + j, o[k][p] / 100, b.f["pctin"])
    ws.write(11, 0, "Revenue from top 10 customers (₹ lakhs)", b.f["txt"])
    ws.write(12, 0, "Revenue from operations (₹ lakhs)", b.f["txt"])
    for j, p in enumerate(P4):
        ws.write_number(12, 1 + j, pl[p]["revenue"], b.f["num"])
        ws.write_formula(11, 1 + j, f"=ROUND({cell(7, 1 + j)}*{cell(12, 1 + j)},2)", b.f["numf"], round(o["top10"][p] / 100 * pl[p]["revenue"], 2))
    ws.write(14, 0, "Export destinations: " + ", ".join(o["export_countries"]), b.f["note"])

    ws = b.sheet("Employees", "Employees by department as on 30 September 2026", [52, 16])
    ws.write_row(3, 0, ["Department", "Number"], b.f["hdr"])
    for i, (k, v) in enumerate(o["employees"].items()):
        ws.write(4 + i, 0, k, b.f["txt"])
        ws.write_number(4 + i, 1, v, b.f["int"])
    n = len(o["employees"])
    ws.write(4 + n, 0, "Total", b.f["txtb"])
    ws.write_formula(4 + n, 1, f"=SUM({cell(4, 1)}:{cell(3 + n, 1)})", b.f["intb"], sum(o["employees"].values()))

    ws = b.sheet("Machinery", "Major plant and machinery installed", [60, 10, 18])
    ws.write_row(3, 0, ["Machine", "Number", "Year of installation"], b.f["hdr"])
    for i, (m, n_, y) in enumerate(o["machines"]):
        ws.write(4 + i, 0, m, b.f["txt"])
        ws.write_number(4 + i, 1, n_, b.f["int"])
        ws.write_number(4 + i, 2, y, b.f["intf"])
    ws = b.sheet("Order_Book", "Order book", [46, 18])
    ws.write_row(3, 0, ["Particulars", "Value"], b.f["hdr"])
    ws.write(4, 0, "Unexecuted orders as on " + o["order_book"]["as_on"] + " (₹ lakhs)", b.f["txt"])
    ws.write_number(4, 1, o["order_book"]["amount"], b.f["num"])
    ws.write(5, 0, "Number of customers in the order book", b.f["txt"])
    ws.write_number(5, 1, o["order_book"]["customers"], b.f["int"])
    b.close()
    return path


# ------------------------------------------------------------------ borrowings -----------------
def borrowings(d, path):
    b = Book(path, "Statement of borrowings")
    ws = b.sheet("Borrowings_30Sep2026", "Statement of borrowings as on 30 September 2026", [26, 30, 14, 14, 26, 36, 46])
    ws.write_row(3, 0, ["Lender", "Facility", "Sanctioned (₹ lakhs)", "Outstanding (₹ lakhs)", "Rate of interest", "Repayment", "Security"], b.f["hdr"])
    bs = d["bs"]["Sep26"]
    rows = [("TL0", bs["b_TL0"]), ("TL1", bs["b_TL1"]), ("VEH", bs["b_VEH"]), ("CC", bs["b_CC"]), ("UNSEC", bs["b_UNSEC"])]
    for i, (k, out) in enumerate(rows):
        L = d["loans"][k]
        r = 4 + i
        ws.write(r, 0, L["lender"], b.f["txt"])
        ws.write(r, 1, L["facility"], b.f["txt"])
        if L["sanctioned"]:
            ws.write_number(r, 2, L["sanctioned"], b.f["num"])
        else:
            ws.write(r, 2, "-", b.f["txt"])
        ws.write_number(r, 3, out, b.f["num"])
        ws.write(r, 4, L["rate"], b.f["txt"])
        ws.write(r, 5, L["tenure"], b.f["txt"])
        ws.write(r, 6, L["security"], b.f["txt"])
    ws.write(9, 1, "Total fund-based borrowings", b.f["txtb"])
    ws.write_formula(9, 3, f"=SUM({cell(4, 3)}:{cell(8, 3)})", b.f["numb"], bs["total_debt"])
    ws.write(11, 0, "Non-fund based limits utilised: bank guarantees ₹45.00 lakhs; letters of credit ₹118.40 lakhs.", b.f["note"])
    ws.write(12, 0, "Classification in restated statements: current maturities ₹" + f"{bs['cur_mat']:.2f}" +
             " lakhs shown under short-term borrowings.", b.f["note"])
    ws.write(13, 0, "Certified by N K Bhatt & Co., Chartered Accountants, on 26 October 2026 (UDIN on the signed copy).", b.f["note"])

    ws = b.sheet("TL-II_Schedule", "Term loan TL-II - repayment schedule (₹ lakhs)", [12, 14, 14, 14])
    ws.write_row(3, 0, ["Month", "Opening", "Principal", "Closing"], b.f["hdr"])
    months = []
    y, m = 2025, 1
    for _ in range(60):
        months.append(f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]}-{y}")
        m += 1
        if m == 13:
            m, y = 1, y + 1
    bal = 720.0
    for i, mo in enumerate(months):
        r = 4 + i
        ws.write(r, 0, mo, b.f["txt"])
        if i == 0:
            ws.write_number(r, 1, 720.0, b.f["num"])
        else:
            ws.write_formula(r, 1, f"={cell(r - 1, 3)}", b.f["numf"], bal)
        ws.write_number(r, 2, 12.0, b.f["num"])
        ws.write_formula(r, 3, f"={cell(r, 1)}-{cell(r, 2)}", b.f["numf"], bal - 12.0)
        bal -= 12.0
    b.close()
    return path


# ------------------------------------------------------------------ licences and other registers ---
def licences(d, path):
    b = Book(path, "Licences and approvals")
    ws = b.sheet("Approvals", "Material licences, registrations and approvals", [44, 38, 24, 22, 26, 40])
    ws.write_row(3, 0, ["Approval", "Issuing authority", "Number", "Date of issue", "Valid up to", "Status"], b.f["hdr"])
    for i, row in enumerate(d["licences"]):
        ws.write_row(4 + i, 0, list(row), b.f["txt"])
    ws.write(5 + len(d["licences"]), 0, "Pending applications: Fire NOC renewal (applied 20 September 2026). Not yet applied: LEI; factory licence renewal (due December 2026).", b.f["note"])
    b.close()
    return path


def group_rpt(d, path):
    b = Book(path, "Group companies and related party transactions")
    ws = b.sheet("Group_Companies", "Group companies (as per materiality policy)", [40, 18, 20, 44, 40, 40])
    ws.write_row(3, 0, ["Name", "LLPIN / CIN", "Date of incorporation", "Registered office", "Nature of business", "Interest of Promoters"], b.f["hdr"])
    for i, (n, g) in enumerate(d["group_companies"].items()):
        ws.write_row(4 + i, 0, [n, g.get("llpin", g.get("cin")), g["incorporated"], g["office"], g["business"],
                                g.get("partners", g.get("directors"))], b.f["txt"])
    ws.write_row(8, 0, ["Financial information (₹ lakhs)", "FY 2023-24", "FY 2024-25", "FY 2025-26"], b.f["hdr"])
    r = 9
    for n, g in d["group_companies"].items():
        for k, lab in (("turnover", "Turnover"), ("pat", "Profit / (loss) after tax"), ("net_worth", "Net worth")):
            ws.write(r, 0, f"{n} - {lab}", b.f["txt"])
            for j, p in enumerate(("FY24", "FY25", "FY26")):
                ws.write_number(r, 1 + j, g["financials"][p][k], b.f["num"])
            r += 1
    ws = b.sheet("RPT", "Related party transactions (₹ lakhs)", [40, 34, 14, 14, 14, 14])
    ws.write_row(3, 0, ["Nature of transaction", "Related party", "H1 FY27", "FY26", "FY25", "FY24"], b.f["hdr"])
    r = 4
    for (nat, party), vals in d["rpt"]["transactions"].items():
        ws.write(r, 0, nat, b.f["txt"])
        ws.write(r, 1, party, b.f["txt"])
        for j, p in enumerate(P4):
            ws.write_number(r, 2 + j, vals.get(p, 0.0), b.f["num"])
        r += 1
    ws.write(r + 1, 0, "All transactions approved by the Board (and by the Audit Committee from 20 July 2026) as being at arm's length.", b.f["note"])
    b.close()
    return path


def objects(d, path):
    b = Book(path, "Objects of the issue - project cost")
    ws = b.sheet("Summary", "Objects of the Fresh Issue and deployment schedule (₹ lakhs)", [70, 16, 16, 16])
    ws.write_row(3, 0, ["Object", "Estimated amount", "FY 2026-27", "FY 2027-28"], b.f["hdr"])
    for i, o in enumerate(d["objects"]):
        r = 4 + i
        ws.write(r, 0, o["object"], b.f["txt"])
        ws.write_formula(r, 1, f"={cell(r, 2)}+{cell(r, 3)}", b.f["numf"], o["amount"])
        ws.write_number(r, 2, o["fy27"], b.f["num"])
        ws.write_number(r, 3, o["fy28"], b.f["num"])
    n = len(d["objects"])
    ws.write(4 + n, 0, "Total of specific objects", b.f["txtb"])
    for col, key in ((1, "amount"), (2, "fy27"), (3, "fy28")):
        ws.write_formula(4 + n, col, f"=SUM({cell(4, col)}:{cell(3 + n, col)})", b.f["numb"], sum(o[key] for o in d["objects"]))
    ws.write(5 + n, 0, "General corporate purposes", b.f["txt"])
    ws.write(5 + n, 1, "[●]", b.f["txt"])
    ws.write(6 + n, 0, "Issue expenses", b.f["txt"])
    ws.write(6 + n, 1, "[●]", b.f["txt"])
    ws.write(8 + n, 0, f"Amount already deployed up to {d['funds_deployed']['as_on']} from internal accruals: ₹{d['funds_deployed']['amount']:.2f} lakhs (to be recouped).", b.f["note"])

    ws = b.sheet("Plant_Machinery", "Plant and machinery - quotation-wise cost (₹ lakhs)", [54, 30, 18, 16, 16, 8, 12, 12, 30])
    ws.write_row(3, 0, ["Item", "Supplier", "Quotation no.", "Date", "Valid till", "Qty", "Unit price", "Amount", "Remarks"], b.f["hdr"])
    for i, m in enumerate(d["machinery"]):
        r = 4 + i
        ws.write_row(r, 0, [m["item"], m["supplier"] + ", " + m["place"], m["quote_no"], m["quote_date"], m["valid_till"]], b.f["txt"])
        ws.write_number(r, 5, m["qty"], b.f["int"])
        ws.write_number(r, 6, m["unit_price"], b.f["num"])
        ws.write_formula(r, 7, f"={cell(r, 5)}*{cell(r, 6)}", b.f["numf"], m["amount"])
        ws.write(r, 8, ("EUR " + f"{m['unit_price_fx']:,} at ₹{m['fx_rate']}/EUR incl. duty and freight") if m["currency"] == "EUR" else m["delivery"], b.f["txt"])
    k = len(d["machinery"])
    ws.write(4 + k, 0, "Total", b.f["txtb"])
    ws.write_formula(4 + k, 7, f"=SUM({cell(4, 7)}:{cell(3 + k, 7)})", b.f["numb"], sum(m["amount"] for m in d["machinery"]))
    ws.write(6 + k, 0, "Quotations exclude GST (input credit available). Civil and electrical work for the new press is funded from internal accruals and is not part of the Objects.", b.f["note"])

    s = d["solar"]
    ws = b.sheet("Solar_Plant", f"Rooftop solar plant {s['capacity_mwp']:.2f} MWp - EPC quotation {s['quote_no']} (₹ lakhs)", [70, 16])
    ws.write_row(3, 0, ["Component", "Amount"], b.f["hdr"])
    for i, (it, amt) in enumerate(s["items"]):
        ws.write(4 + i, 0, it, b.f["txt"])
        ws.write_number(4 + i, 1, amt, b.f["num"])
    ws.write(4 + len(s["items"]), 0, "Total", b.f["txtb"])
    ws.write_formula(4 + len(s["items"]), 1, f"=SUM({cell(4, 1)}:{cell(3 + len(s['items']), 1)})", b.f["numb"], s["amount"])
    b.close()
    return path


def insurance_ip(d, path):
    b = Book(path, "Insurance and IP register")
    ws = b.sheet("Insurance", "Insurance policies in force", [48, 40, 22, 16, 22])
    ws.write_row(3, 0, ["Policy", "Insurer", "Policy number", "Sum insured (₹ lakhs)", "Valid till"], b.f["hdr"])
    for i, row in enumerate(d["insurance"]):
        ws.write(4 + i, 0, row[0], b.f["txt"])
        ws.write(4 + i, 1, row[1], b.f["txt"])
        ws.write(4 + i, 2, row[2], b.f["txt"])
        ws.write_number(4 + i, 3, row[3], b.f["num"])
        ws.write(4 + i, 4, row[4], b.f["txt"])
    ws = b.sheet("Trademarks", "Intellectual property", [36, 10, 12, 18, 20, 44])
    ws.write_row(3, 0, ["Mark", "Class", "Application no.", "Date of application", "Status", "Remarks"], b.f["hdr"])
    for i, row in enumerate(d["ip"]):
        ws.write_row(4 + i, 0, list(row), b.f["txt"])
    b.close()
    return path


def index(files, path):
    b = Book(path, "Document index")
    ws = b.sheet("Index", "Issuer document bundle - index (prepared for the BRLM data room)", [6, 18, 56, 10, 10, 12, 50])
    ws.write_row(3, 0, ["Sr.", "Folder", "File", "Format", "Pages", "Size (KB)", "Description"], b.f["hdr"])
    for i, f in enumerate(files):
        ws.write_number(4 + i, 0, i + 1, b.f["intf"])
        ws.write_row(4 + i, 1, [f["folder"], f["file"], f["format"]], b.f["txt"])
        if f.get("pages"):
            ws.write_number(4 + i, 4, f["pages"], b.f["int"])
        else:
            ws.write(4 + i, 4, "-", b.f["txt"])
        ws.write_number(4 + i, 5, f["kb"], b.f["int"])
        ws.write(4 + i, 6, f["desc"], b.f["txt"])
    b.close()
    return path
