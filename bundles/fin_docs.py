"""Financial documents: restated financial information (ICDR), audited financial statements for three
years, and the statutory auditor's certificates (KPIs, working capital, funds deployed, tax benefits)."""
from __future__ import annotations

import copy

import issuer as I
from common import inr, num, pct
from pdfkit import Doc

R = I.r2


def auditor_letterhead(d):
    a = d["advisers"]["auditor"]
    return (a["name"].upper() + "  |  CHARTERED ACCOUNTANTS",
            a["address"] + "  |  Tel: +91 79 2754 3180  |  nkbhatt-synthetic.example",
            f"Firm Registration No. {a['frn']}  |  Peer Review Certificate No. {a['peer_review_cert']}")


def company_letterhead(d):
    c = d["company"]
    return (c["name"].upper(), "Regd. Office: " + c["registered_office"],
            f"CIN: {c['cin']}  |  Tel: {c['telephone']}  |  Email: {c['email']}  |  GSTIN: {c['gstin']}")


def auditor_sign(doc, d, date, place="Ahmedabad", udin_seq="01"):
    a = d["advisers"]["auditor"]
    doc.signature([f"For <b>{a['name']}</b>", "Chartered Accountants", f"Firm Registration No. {a['frn']}", "",
                   "Sd/-", "", f"<b>{a['partner']}</b>", "Partner", f"Membership No. {a['membership']}",
                   f"UDIN: 26{a['membership']}BKSYN{udin_seq}{udin_seq}4"],
                  left=[f"Place: {place}", f"Date: {date}"])


# ------------------------------------------------------------------ column views ---------------
def restated_cols(d):
    out = []
    for p in ["H1FY27", "FY26", "FY25", "FY24"]:
        k = I.CLOSE[p]
        out.append({"p": p, "label": I.DATE_LABEL[k].replace("September", "Sep").replace("March", "March"),
                    "plabel": I.PERIOD_LABEL[p].replace("Six months ended", "Six months ended"),
                    "bs": d["bs"][k], "bs_open": d["bs"][I.OPEN[p]], "pl": d["pl"][p], "cf": d["cf"][p],
                    "ppe": d["ppe"][p], "close": k})
    return out


def audited_cols(d, year):
    """Two columns (current, previous) using audited figures."""
    prev = {"FY24": "FY23", "FY25": "FY24", "FY26": "FY25"}[year]
    out = []
    for p in (year, prev):
        k = I.CLOSE[p]
        pl = copy.deepcopy(d["pl"][p])
        bs = copy.deepcopy(d["bs"][k])
        cf = copy.deepcopy(d["cf"][p])
        if p in d["audited"]:
            pl = d["audited"][p]["pl"]
            bs = d["audited"][p]["bs"]
            diff = R(pl["pbt"] - d["pl"][p]["pbt"])
            cf["pbt"] = pl["pbt"]
            cf["op_before_wc"] = R(cf["op_before_wc"] + diff)
            cf["d_provisions"] = R(cf["d_provisions"] - diff)
        out.append({"p": p, "label": I.DATE_LABEL[k], "plabel": I.PERIOD_LABEL[p], "bs": bs,
                    "bs_open": d["audited"][I.CLOSE[prev]]["bs"] if False else None,
                    "pl": pl, "cf": cf, "ppe": d["ppe"][p], "close": k})
    return out


def _w(n_cols):
    lab = 174 - 12 - 22 * n_cols
    return [lab, 12] + [22] * n_cols


def _row(label, note, vals, dp=2):
    return [label, note] + [inr(v, dp) for v in vals]


# ------------------------------------------------------------------ primary statements ---------
def balance_sheet(doc, cols, title, notes):
    n = notes
    hdr = ["Particulars", "Note"] + [f"As at {c['label']}" for c in cols]
    g = lambda f: [f(c["bs"]) for c in cols]
    rows = [hdr,
            ["<b>I. EQUITY AND LIABILITIES</b>", ""] + [""] * len(cols),
            ["<b>(1) Shareholders' funds</b>", ""] + [""] * len(cols),
            _row("(a) Share capital", n["sc"], g(lambda b: b["share_capital"])),
            _row("(b) Reserves and surplus", n["rs"], g(lambda b: b["other_equity"])),
            ["<b>(2) Non-current liabilities</b>", ""] + [""] * len(cols),
            _row("(a) Long-term borrowings", n["ltb"], g(lambda b: b["lt_borrowings"])),
            _row("(b) Deferred tax liabilities (net)", n["dtl"], g(lambda b: b["dtl"])),
            _row("(c) Long-term provisions", n["ltp"], g(lambda b: b["gratuity_nc"])),
            ["<b>(3) Current liabilities</b>", ""] + [""] * len(cols),
            _row("(a) Short-term borrowings", n["stb"], g(lambda b: b["st_borrowings"])),
            _row("(b) Trade payables", n["tp"], [None] * 0 + g(lambda b: b["payables"])),
            _row("&nbsp;&nbsp;&nbsp;(A) total outstanding dues of micro and small enterprises", "", g(lambda b: msme(b["payables"]))),
            _row("&nbsp;&nbsp;&nbsp;(B) total outstanding dues of creditors other than micro and small enterprises", "",
                 g(lambda b: R(b["payables"] - msme(b["payables"])))),
            _row("(c) Other current liabilities", n["ocl"], g(lambda b: b["ocl"])),
            _row("(d) Short-term provisions", n["stp"], g(lambda b: R(b["gratuity_c"] + b["tax_liab"]))),
            _row("<b>TOTAL</b>", "", g(lambda b: b["total_liabilities"])),
            ["<b>II. ASSETS</b>", ""] + [""] * len(cols),
            ["<b>(1) Non-current assets</b>", ""] + [""] * len(cols),
            _row("(a) Property, plant and equipment and intangible assets", "", [None] * 0 + g(lambda b: R(b["ppe_net"] + b["cwip"]))),
            _row("&nbsp;&nbsp;&nbsp;(i) Property, plant and equipment", n["ppe"], g(lambda b: b["ppe_net"])),
            _row("&nbsp;&nbsp;&nbsp;(ii) Capital work-in-progress", n["cwip"], g(lambda b: b["cwip"])),
            _row("(b) Long-term loans and advances", n["ltla"], g(lambda b: R(b["cap_adv"] + b["deposits"]))),
            ["<b>(2) Current assets</b>", ""] + [""] * len(cols),
            _row("(a) Inventories", n["inv"], g(lambda b: b["inventories"])),
            _row("(b) Trade receivables", n["tr"], g(lambda b: b["receivables"])),
            _row("(c) Cash and bank balances", n["cash"], g(lambda b: b["cash_total"])),
            _row("(d) Short-term loans and advances", n["stla"], g(lambda b: R(b["oca"] * 0.85))),
            _row("(e) Other current assets", n["oca"], g(lambda b: R(b["oca"] - R(b["oca"] * 0.85)))),
            _row("<b>TOTAL</b>", "", g(lambda b: b["total_assets"])),
            ]
    doc.h1(title)
    doc.p("(All amounts in ₹ lakhs, unless otherwise stated)", "right")
    doc.table(rows, _w(len(cols)), num_cols=range(2, 2 + len(cols)), total_rows=(16, 29))


def msme(payables):
    return R(payables * 0.22)


def profit_and_loss(doc, cols, title, notes, restated=True):
    n = notes
    g = lambda f: [f(c["pl"]) for c in cols]
    hdr = ["Particulars", "Note"] + [c["plabel"] for c in cols]
    rows = [hdr,
            _row("I. Revenue from operations", n["rev"], g(lambda x: x["revenue"])),
            _row("II. Other income", n["oi"], g(lambda x: x["oi"])),
            _row("<b>III. Total income (I + II)</b>", "", g(lambda x: R(x["revenue"] + x["oi"]))),
            ["<b>IV. Expenses</b>", ""] + [""] * len(cols),
            _row("Cost of materials consumed", n["comc"], g(lambda x: x["comc"])),
            _row("Changes in inventories of finished goods and work-in-progress", n["chg"], g(lambda x: x["inv_change"])),
            _row("Employee benefits expense", n["emp"], g(lambda x: x["emp"])),
            _row("Finance costs", n["fin"], g(lambda x: x["fin"])),
            _row("Depreciation and amortisation expense", n["ppe"], g(lambda x: x["dep"])),
            _row("Other expenses", n["oe"], g(lambda x: x["oe"])),
            _row("<b>Total expenses (IV)</b>", "", g(lambda x: R(x["comc"] + x["inv_change"] + x["emp"] + x["fin"] + x["dep"] + x["oe"]))),
            _row("<b>V. Profit before exceptional and extraordinary items and tax (III - IV)</b>", "", g(lambda x: x["pbt"])),
            _row("VI. Exceptional items", "", g(lambda x: 0.0)),
            _row("VII. Extraordinary items", "", g(lambda x: 0.0)),
            _row("<b>VIII. Profit before tax</b>", "", g(lambda x: x["pbt"])),
            ["IX. Tax expense:", n["tax"]] + [""] * len(cols),
            _row("&nbsp;&nbsp;&nbsp;(1) Current tax", "", g(lambda x: x["tax_current"])),
            _row("&nbsp;&nbsp;&nbsp;(2) Deferred tax charge / (credit)", "", g(lambda x: x["tax_deferred"])),
            _row("<b>X. Profit for the period / year (VIII - IX)</b>", "", g(lambda x: x["pat"])),
            ["XI. Earnings per equity share (face value ₹10 each)", n["eps"]] + [""] * len(cols),
            _row("&nbsp;&nbsp;&nbsp;(1) Basic (₹)" + (" (bonus adjusted)" if restated else ""), "", g(lambda x: eps_of(x, restated, cols))),
            _row("&nbsp;&nbsp;&nbsp;(2) Diluted (₹)" + (" (bonus adjusted)" if restated else ""), "", g(lambda x: eps_of(x, restated, cols))),
            ]
    doc.h1(title)
    doc.p("(All amounts in ₹ lakhs, unless otherwise stated)", "right")
    doc.table(rows, _w(len(cols)), num_cols=range(2, 2 + len(cols)), total_rows=(3, 11, 19))
    if restated:
        doc.p("Note: EPS for the six months ended 30 September 2026 is not annualised. EPS for all periods has been "
              "adjusted for the bonus issue of 80,00,000 equity shares allotted on 5 August 2026, as required by AS 20.", "small")


def eps_of(x, restated, cols):
    shares = I.SHARES_PRE_ISSUE if restated else I.SHARES_PRE_BONUS
    return round(x["pat"] * 1e5 / shares, 2)


def cash_flow(doc, cols, title):
    g = lambda f: [f(c["cf"]) for c in cols]
    hdr = ["Particulars", ""] + [c["plabel"] for c in cols]
    rows = [hdr,
            ["<b>A. Cash flow from operating activities</b>", ""] + [""] * len(cols),
            _row("Profit before tax", "", g(lambda c: c["pbt"])),
            ["Adjustments for:", ""] + [""] * len(cols),
            _row("Depreciation and amortisation expense", "", g(lambda c: c["dep"])),
            _row("Finance costs", "", g(lambda c: c["fin"])),
            _row("Interest income", "", g(lambda c: c["interest_income"])),
            _row("Profit on sale of property, plant and equipment", "", g(lambda c: c["profit_on_sale"])),
            _row("<b>Operating profit before working capital changes</b>", "", g(lambda c: c["op_before_wc"])),
            ["Movements in working capital:", ""] + [""] * len(cols),
            _row("(Increase) / decrease in inventories", "", g(lambda c: c["d_inventories"])),
            _row("(Increase) / decrease in trade receivables", "", g(lambda c: c["d_receivables"])),
            _row("(Increase) / decrease in loans, advances and other assets", "", g(lambda c: c["d_oca"])),
            _row("Increase / (decrease) in trade payables", "", g(lambda c: c["d_payables"])),
            _row("Increase / (decrease) in other current liabilities", "", g(lambda c: c["d_ocl"])),
            _row("Increase / (decrease) in provisions", "", g(lambda c: c["d_provisions"])),
            _row("<b>Cash generated from operations</b>", "", g(lambda c: c["cash_generated"])),
            _row("Income taxes paid (net of refunds)", "", g(lambda c: c["tax_paid"])),
            _row("<b>Net cash flow from operating activities (A)</b>", "", g(lambda c: c["cfo"])),
            ["<b>B. Cash flow from investing activities</b>", ""] + [""] * len(cols),
            _row("Purchase of property, plant and equipment (including capital work-in-progress and capital advances)", "", g(lambda c: c["capex"])),
            _row("Proceeds from sale of property, plant and equipment", "", g(lambda c: c["sale_proceeds"])),
            _row("Interest received", "", g(lambda c: c["interest_received"])),
            _row("(Investment in) / redemption of margin money deposits", "", g(lambda c: c["d_fd_lien"])),
            _row("<b>Net cash flow used in investing activities (B)</b>", "", g(lambda c: c["cfi"])),
            ["<b>C. Cash flow from financing activities</b>", ""] + [""] * len(cols),
            _row("Proceeds from long-term borrowings", "", g(lambda c: c["lt_proceeds"])),
            _row("Repayment of long-term borrowings", "", g(lambda c: c["lt_repaid"])),
            _row("Net proceeds from / (repayment of) short-term borrowings", "", g(lambda c: c["d_cc"])),
            _row("Net proceeds from / (repayment of) unsecured loans from Promoter", "", g(lambda c: c["d_unsec"])),
            _row("Finance costs paid", "", g(lambda c: c["fin_paid"])),
            _row("<b>Net cash flow from / (used in) financing activities (C)</b>", "", g(lambda c: c["cff"])),
            _row("<b>Net increase / (decrease) in cash and cash equivalents (A + B + C)</b>", "", g(lambda c: c["net_change"])),
            _row("Cash and cash equivalents at the beginning of the period", "", g(lambda c: c["cash_open"])),
            _row("<b>Cash and cash equivalents at the end of the period</b>", "", g(lambda c: c["cash_close"])),
            ]
    doc.h1(title)
    doc.p("(All amounts in ₹ lakhs, unless otherwise stated)", "right")
    doc.table(rows, _w(len(cols)), num_cols=range(2, 2 + len(cols)), total_rows=(18, 24, 31, 34))
    doc.p("Notes: (1) The cash flow statement has been prepared under the indirect method set out in Accounting "
          "Standard (AS) 3, 'Cash Flow Statements'. (2) Cash and cash equivalents exclude margin money deposits held "
          "as security against bank guarantees and letters of credit, which are shown under investing activities.", "small")


# ------------------------------------------------------------------ notes -------------------------
POLICIES = [
    ("Basis of preparation", "The financial statements have been prepared under the historical cost convention on an "
     "accrual basis of accounting in accordance with the Generally Accepted Accounting Principles in India (Indian GAAP), "
     "including the Accounting Standards notified under Section 133 of the Companies Act, 2013 read with Rule 7 of the "
     "Companies (Accounts) Rules, 2014 and the Companies (Accounting Standards) Rules, 2021, and the presentation "
     "requirements of Division I of Schedule III to the Companies Act, 2013. The Company is a Small and Medium-sized "
     "Company (SMC) up to FY 2023-24 and a non-SMC from FY 2024-25; accordingly the exemptions available to SMCs have "
     "not been availed for any period presented."),
    ("Use of estimates", "The preparation of financial statements requires management to make estimates and assumptions "
     "that affect the reported amounts of assets, liabilities, revenue and expenses and the disclosure of contingent "
     "liabilities. Estimates include useful lives of property, plant and equipment, provision for employee benefits, "
     "provision for doubtful receivables and provision for taxation. Differences between actual results and estimates "
     "are recognised in the period in which the results are known."),
    ("Operating cycle", "Based on the nature of products and the time between the acquisition of materials and their "
     "realisation in cash, the Company has determined its operating cycle as twelve months for the purpose of "
     "classification of assets and liabilities as current and non-current."),
    ("Property, plant and equipment", "Property, plant and equipment are stated at cost of acquisition less accumulated "
     "depreciation and impairment, if any. Cost includes freight, non-refundable duties and taxes, and expenses "
     "directly attributable to bringing the asset to its working condition, including borrowing costs on qualifying "
     "assets. Depreciation is provided on the straight-line method over the useful lives prescribed in Schedule II to "
     "the Companies Act, 2013. Leasehold land is amortised over the period of the lease. Assets costing up to ₹5,000 "
     "are fully depreciated in the year of purchase."),
    ("Capital work-in-progress", "Capital work-in-progress comprises the cost of assets not ready for their intended use "
     "at the balance sheet date, including directly attributable expenditure."),
    ("Inventories", "Raw materials, packing materials and stores and spares are valued at the lower of cost and net "
     "realisable value; cost is determined on a weighted-average basis. Work-in-progress and finished goods are valued at "
     "the lower of cost and net realisable value; cost includes materials, labour and a proportion of manufacturing "
     "overheads based on normal operating capacity. Printing cylinders are expensed as job-work charges when billed."),
    ("Revenue recognition", "Revenue from sale of goods is recognised when significant risks and rewards of ownership "
     "are transferred to the buyer, which generally coincides with dispatch or delivery as per the terms of sale, and "
     "is stated net of goods and services tax, trade discounts and returns. Export incentives are recognised when the "
     "right to receive them is established and there is no significant uncertainty about realisation. Sale of scrap is "
     "recognised on dispatch."),
    ("Foreign currency transactions", "Transactions in foreign currency are recorded at the exchange rate on the date of "
     "the transaction. Monetary items outstanding at the balance sheet date are restated at the closing rate and the "
     "resulting differences are recognised in the statement of profit and loss."),
    ("Employee benefits", "Contributions to provident fund and employees' state insurance are defined contribution plans "
     "charged to the statement of profit and loss when due. Gratuity is a defined benefit obligation determined by an "
     "independent actuary using the projected unit credit method at each balance sheet date; actuarial gains and losses "
     "are recognised in the statement of profit and loss. The gratuity scheme is unfunded. Leave encashment is not "
     "permitted to be carried forward beyond the year."),
    ("Borrowing costs", "Borrowing costs directly attributable to the acquisition or construction of qualifying assets are "
     "capitalised until the asset is ready for its intended use. Other borrowing costs are expensed in the period in "
     "which they are incurred."),
    ("Taxes on income", "Current tax is determined at the amount expected to be paid under the Income-tax Act, 1961. The "
     "Company has opted for the concessional rate under Section 115BAA from AY 2020-21. Deferred tax is recognised on "
     "timing differences between taxable and accounting income at the tax rates enacted or substantively enacted at "
     "the balance sheet date, subject to prudence."),
    ("Leases", "Lease rentals under operating leases are recognised as an expense in the statement of profit and loss on a "
     "straight-line basis over the lease term."),
    ("Government grants and EPCG", "Customs duty saved under the Export Promotion Capital Goods scheme is not recognised "
     "as income; the export obligation outstanding is disclosed as a contingent liability."),
    ("Earnings per share", "Basic earnings per share is computed by dividing the profit for the period by the weighted "
     "average number of equity shares outstanding. The number of shares is adjusted for bonus issues for all periods "
     "presented. There are no dilutive potential equity shares."),
    ("Provisions and contingent liabilities", "A provision is recognised when the Company has a present obligation as a "
     "result of a past event, it is probable that an outflow of resources will be required and a reliable estimate can "
     "be made. Contingent liabilities are disclosed in the notes; contingent assets are neither recognised nor disclosed."),
    ("Cash and cash equivalents", "Cash and cash equivalents comprise cash on hand and balances with banks in current "
     "accounts. Deposits with banks held as margin money are disclosed under other bank balances."),
    ("Segment reporting", "The Company operates in a single business segment, manufacture of flexible packaging "
     "materials, and its operations are primarily in India; accordingly no separate segment disclosures are given "
     "under AS 17 beyond the geographical information on revenue."),
]


def policies(doc):
    for i, (h, t) in enumerate(POLICIES, 1):
        doc.h3(f"{chr(96 + i) if i <= 26 else i}) {h}")
        doc.p(t)


def note_share_capital(doc, d, cols, no):
    doc.h2(f"Note {no}: Share capital")
    rows = [["Particulars"] + [f"As at {c['label']}" for c in cols]]
    auth = lambda c: 1500.00 if c["close"] == "Sep26" else (250.00 if c["close"] >= "Mar20" else 100.00)
    shares_auth = lambda c: 1_50_00_000 if c["close"] == "Sep26" else 25_00_000
    shares_iss = lambda c: I.SHARES_PRE_ISSUE if c["close"] == "Sep26" else I.SHARES_PRE_BONUS
    rows.append(["<b>Authorised</b>"] + [""] * len(cols))
    rows.append(["Equity shares of ₹10 each (number)"] + [num(shares_auth(c)) for c in cols])
    rows.append(["Amount"] + [inr(shares_auth(c) * 10 / 1e5) for c in cols])
    rows.append(["<b>Issued, subscribed and fully paid up</b>"] + [""] * len(cols))
    rows.append(["Equity shares of ₹10 each (number)"] + [num(shares_iss(c)) for c in cols])
    rows.append(["<b>Amount</b>"] + [inr(c["bs"]["share_capital"]) for c in cols])
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), bold_rows=(6,))
    doc.h3("(a) Reconciliation of the number of shares outstanding")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    open_sh = lambda c: I.SHARES_PRE_BONUS
    rows.append(["Shares outstanding at the beginning of the period"] + [num(open_sh(c)) for c in cols])
    rows.append(["Add: bonus shares allotted on 5 August 2026 (4:1)"] + [num(80_00_000 if c["close"] == "Sep26" else 0) for c in cols])
    rows.append(["Shares outstanding at the end of the period"] + [num(shares_iss(c)) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(3,))
    doc.h3("(b) Rights, preferences and restrictions")
    doc.p("The Company has one class of equity shares with a face value of ₹10 per share. Each holder is entitled to one "
          "vote per share. Dividends, if proposed by the Board, are subject to the approval of the shareholders at the "
          "general meeting. In the event of liquidation, holders are entitled to the remaining assets after "
          "distribution of preferential amounts, in proportion to their shareholding.")
    doc.h3("(c) Shareholders holding more than 5% of the equity shares")
    h = d["holdings"]
    rows = [["Name of shareholder", "Number of shares (latest)", "% holding", "Number of shares (31 March)", "% holding"]]
    for name in ("Hemant Ramniklal Desai", "Kavita Hemant Desai", "Parth Hemant Desai"):
        rows.append([name, num(h["pre_issue"][name]), pct(h["pct_pre_issue"][name]), num(h["pre_bonus"][name]),
                     pct(100 * h["pre_bonus"][name] / I.SHARES_PRE_BONUS)])
    doc.table(rows, [64, 30, 22, 36, 22], num_cols=(1, 2, 3, 4))
    doc.h3("(d) Shareholding of Promoters")
    rows = [["Promoter name", "Number of shares", "% of total shares", "% change during the period"]]
    for name in ("Hemant Ramniklal Desai", "Kavita Hemant Desai"):
        rows.append([name, num(h["pre_issue"][name]), pct(h["pct_pre_issue"][name]), "Nil (bonus shares only)"])
    doc.table(rows, [70, 34, 32, 38], num_cols=(1, 2))
    doc.h3("(e) Bonus shares and shares issued for consideration other than cash in the last five years")
    doc.p("The Company allotted 80,00,000 fully paid-up equity shares of ₹10 each as bonus shares on 5 August 2026 by "
          "capitalising ₹600.00 lakhs from the securities premium account and ₹200.00 lakhs from the surplus in the "
          "statement of profit and loss. On 28 March 2020, 10,00,000 equity shares were allotted at ₹55 per share "
          "(including a premium of ₹45 per share) on conversion of unsecured loans of ₹550.00 lakhs.")


def note_reserves(doc, cols, no):
    doc.h2(f"Note {no}: Reserves and surplus")
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    rows = [["Particulars"] + [f"As at {c['label']}" for c in cols]]
    rows.append(["<b>(a) Securities premium</b>"] + [""] * len(cols))
    rows.append(["Opening balance"] + [inr(600.00) for c in cols])
    rows.append(["Less: utilised for issue of bonus shares"] + [inr(-600.00 if c["close"] == "Sep26" else 0) for c in cols])
    rows.append(["Closing balance"] + [inr(c["bs"]["securities_premium"]) for c in cols])
    rows.append(["<b>(b) Surplus in the statement of profit and loss</b>"] + [""] * len(cols))
    op = lambda c: R(c["bs"]["retained_earnings"] - c["pl"]["pat"] + (200.00 if c["close"] == "Sep26" else 0))
    rows.append(["Opening balance"] + [inr(op(c)) for c in cols])
    rows.append(["Add: profit for the period"] + [inr(c["pl"]["pat"]) for c in cols])
    rows.append(["Less: utilised for issue of bonus shares"] + [inr(-200.00 if c["close"] == "Sep26" else 0) for c in cols])
    rows.append(["Closing balance"] + [inr(c["bs"]["retained_earnings"]) for c in cols])
    rows.append(["<b>Total reserves and surplus</b>"] + [inr(c["bs"]["other_equity"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(10,))


def note_borrowings(doc, d, cols, no_lt, no_st):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no_lt}: Long-term borrowings")
    rows = [["Particulars"] + [f"As at {c['label']}" for c in cols]]
    b = lambda c, k: c["bs"]["b_" + k]
    cm = lambda c, k: I.CUR_MAT[k][c["close"]]
    rows.append(["<b>Secured</b>"] + [""] * len(cols))
    rows.append(["Term loans from banks - Kalindi Bank Limited"] + [inr(b(c, "TL0") + b(c, "TL1")) for c in cols])
    rows.append(["Vehicle loans from non-banking financial company"] + [inr(b(c, "VEH")) for c in cols])
    rows.append(["Less: current maturities shown under short-term borrowings"] + [inr(-c["bs"]["cur_mat"]) for c in cols])
    rows.append(["<b>Unsecured</b>"] + [""] * len(cols))
    rows.append(["Loan from Promoter (related party)"] + [inr(b(c, "UNSEC")) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["bs"]["lt_borrowings"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(7,))
    doc.h3("Terms of borrowings")
    rows = [["Lender / facility", "Sanctioned (₹ lakhs)", "Rate of interest", "Repayment", "Security"]]
    for k in ("TL0", "TL1", "VEH", "CC", "UNSEC"):
        L = d["loans"][k]
        rows.append([f"{L['lender']} - {L['facility']} (sanctioned {L['sanction_date']})",
                     inr(L["sanctioned"]) if L["sanctioned"] else "-", L["rate"], L["tenure"], L["security"]])
    doc.table(rows, [40, 18, 30, 40, 46], num_cols=(1,), font_size=7)
    doc.p("The Company has not defaulted in the repayment of principal or interest to any lender during the periods "
          "presented. Quarterly stock and book-debt statements filed with the bank are in agreement with the books of "
          "account, except for timing differences in the quarter ended 30 June 2025 that were not material.", "small")
    doc.h2(f"Note {no_st}: Short-term borrowings")
    rows = [["Particulars"] + [f"As at {c['label']}" for c in cols]]
    rows.append(["Secured - cash credit from Kalindi Bank Limited (repayable on demand)"] + [inr(b(c, "CC")) for c in cols])
    rows.append(["Current maturities of long-term borrowings"] + [inr(c["bs"]["cur_mat"]) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["bs"]["st_borrowings"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(3,))


def note_simple(doc, cols, no, title, items, src="bs"):
    """items: list of (label, function(col) -> value). Adds a total row."""
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: {title}")
    head = [f"As at {c['label']}" for c in cols] if src == "bs" else [c["plabel"] for c in cols]
    rows = [["Particulars"] + head]
    tot = [0.0] * len(cols)
    for lab, f in items:
        vals = [f(c) for c in cols]
        tot = [t + v for t, v in zip(tot, vals)]
        rows.append([lab] + [inr(v) for v in vals])
    rows.append(["<b>Total</b>"] + [inr(R(t)) for t in tot])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(len(rows) - 1,))


def ageing_tables(doc, cols, kind):
    """Schedule III ageing for receivables or payables, for the latest two dates."""
    for c in cols[:2]:
        b = c["bs"]
        if kind == "rec":
            disputed = 23.86 if c["close"] in ("Sep26", "Mar26") else 0.0
            undisp = R(b["receivables"] - disputed)
            splits = [0.925, 0.041, 0.020, 0.009, 0.005]
            vals = [R(undisp * s) for s in splits[:-1]]
            vals.append(R(undisp - sum(vals)))
            hdr = ["Particulars", "< 6 months", "6 months - 1 year", "1-2 years", "2-3 years", "> 3 years", "Total"]
            rows = [hdr, ["Undisputed trade receivables - considered good"] + [inr(v) for v in vals] + [inr(undisp)],
                    ["Disputed trade receivables - considered good"] + ["-", "-", inr(disputed), "-", "-", inr(disputed)],
                    ["<b>Total</b>"] + [inr(vals[0]), inr(vals[1]), inr(R(vals[2] + disputed)), inr(vals[3]), inr(vals[4]), inr(b["receivables"])]]
            doc.h3(f"Trade receivables ageing as at {c['label']} (from the due date of payment)")
            doc.table(rows, [52, 20, 22, 20, 20, 20, 20], num_cols=range(1, 7), total_rows=(3,))
        else:
            m = msme(b["payables"])
            o = R(b["payables"] - m)
            sp = [0.968, 0.020, 0.007]
            mv = [R(m * s) for s in sp]
            mv.append(R(m - sum(mv)))
            ov = [R(o * s) for s in sp]
            ov.append(R(o - sum(ov)))
            hdr = ["Particulars", "< 1 year", "1-2 years", "2-3 years", "> 3 years", "Total"]
            rows = [hdr, ["MSME"] + [inr(v) for v in mv] + [inr(m)], ["Others"] + [inr(v) for v in ov] + [inr(o)],
                    ["Disputed dues - MSME", "-", "-", "-", "-", "-"], ["Disputed dues - others", "-", "-", "-", "-", "-"],
                    ["<b>Total</b>"] + [inr(R(a + b_)) for a, b_ in zip(mv, ov)] + [inr(b["payables"])]]
            doc.h3(f"Trade payables ageing as at {c['label']} (from the due date of payment)")
            doc.table(rows, [54, 24, 24, 24, 24, 24], num_cols=range(1, 6), total_rows=(5,))


def note_ppe(doc, cols, no):
    doc.h2(f"Note {no}: Property, plant and equipment")
    for c in cols:
        rows = [["Asset class", "Gross block opening", "Additions", "Deletions", "Gross block closing", "Acc. dep. opening",
                 "For the period", "On deletions", "Acc. dep. closing", "Net block closing", "Net block opening"]]
        tot = [0.0] * 10
        for k in I.PPE_CLASSES:
            r = c["ppe"][k]
            v = [r["gross_open"], r["add"], r["del"], r["gross_close"], r["acc_open"], r["dep"], r["acc_del"],
                 r["acc_close"], r["nbv_close"], r["nbv_open"]]
            tot = [a + b for a, b in zip(tot, v)]
            rows.append([k] + [inr(x) for x in v])
        rows.append(["<b>Total</b>"] + [inr(R(x)) for x in tot])
        doc.h3(c["plabel"])
        doc.table(rows, [26] + [14.8] * 10, num_cols=range(1, 11), total_rows=(len(rows) - 1,))
    doc.p("Title deeds of immovable property: the leasehold land at Sanand-II is held under a lease deed dated 12 December "
          "2012 executed by Gujarat Industrial Development Corporation in the name of the Company (then Ashtavira Flexipak "
          "Private Limited); the name change on conversion is under intimation to GIDC. No proceedings are pending "
          "against the Company under the Benami Transactions (Prohibition) Act, 1988.", "small")


def note_cwip(doc, cols, no):
    doc.h2(f"Note {no}: Capital work-in-progress")
    rows = [["CWIP ageing", "< 1 year", "1-2 years", "2-3 years", "> 3 years", "Total"]]
    for c in cols:
        v = c["bs"]["cwip"]
        rows.append([f"Projects in progress as at {c['label']}", inr(v), "-", "-", "-", inr(v)])
    doc.table(rows, [62, 22, 22, 22, 22, 24], num_cols=range(1, 6))
    doc.p("Capital work-in-progress represents the extension of the finished-goods block and the effluent-treatment "
          "upgrade at Sanand-II. No project is overdue or has exceeded its original cost.", "small")


def note_revenue(doc, cols, no):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: Revenue from operations")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    rows.append(["Sale of products - domestic"] + [inr(c["pl"]["domestic"]) for c in cols])
    rows.append(["Sale of products - exports"] + [inr(c["pl"]["exports"]) for c in cols])
    rows.append(["Other operating revenue - sale of scrap"] + [inr(c["pl"]["scrap"]) for c in cols])
    rows.append(["Other operating revenue - export incentives (RoDTEP)"] + [inr(c["pl"]["export_incentive"]) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["pl"]["revenue"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(5,))
    doc.h3("Sale of products by product category")
    rows = [["Product category"] + [c["plabel"] for c in cols]]
    for prod, mix in I.OPS["product_mix"].items():
        rows.append([prod] + [inr(R(c["pl"]["sale_of_products"] * mix.get(c["p"], mix["FY24"]) / 100)) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))


def note_other_income(doc, cols, no):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: Other income")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    for k in cols[0]["pl"]["oi_detail"]:
        rows.append([k] + [inr(c["pl"]["oi_detail"][k]) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["pl"]["oi"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(len(rows) - 1,))


def note_materials(doc, d, cols, no_m, no_c):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no_m}: Cost of materials consumed")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    op = lambda c: d["bs"][I.OPEN[c["p"]]]["rm"]
    rows.append(["Opening stock of raw materials"] + [inr(op(c)) for c in cols])
    rows.append(["Add: purchases"] + [inr(c["pl"]["rm_purchases"]) for c in cols])
    rows.append(["Less: closing stock of raw materials"] + [inr(-c["bs"]["rm"]) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["pl"]["comc"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(4,))
    doc.h3("Materials consumed by category (%)")
    mix = [("BOPP, PET and metallised films", 46.5), ("Polyethylene granules (LDPE / LLDPE)", 21.8),
           ("Aluminium foil", 6.9), ("Printing inks and solvents", 13.6), ("Adhesives", 7.4), ("Zippers, spouts and others", 3.8)]
    rows = [["Category"] + [c["plabel"] for c in cols]]
    for name, sh in mix:
        rows.append([name] + [inr(R(c["pl"]["comc"] * sh / 100)) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))
    doc.h2(f"Note {no_c}: Changes in inventories of finished goods and work-in-progress")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    o = lambda c: d["bs"][I.OPEN[c["p"]]]
    rows.append(["Opening - finished goods"] + [inr(o(c)["fg"]) for c in cols])
    rows.append(["Opening - work-in-progress"] + [inr(o(c)["wip"]) for c in cols])
    rows.append(["Less: closing - finished goods"] + [inr(-c["bs"]["fg"]) for c in cols])
    rows.append(["Less: closing - work-in-progress"] + [inr(-c["bs"]["wip"]) for c in cols])
    rows.append(["<b>(Increase) / decrease</b>"] + [inr(c["pl"]["inv_change"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(5,))


def note_employee(doc, cols, no):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: Employee benefits expense")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    sal = lambda c: R(c["pl"]["emp"] - c["pl"]["gratuity_exp"] - R(c["pl"]["emp"] * 0.071) - R(c["pl"]["emp"] * 0.024))
    rows.append(["Salaries, wages, bonus and directors' remuneration"] + [inr(sal(c)) for c in cols])
    rows.append(["Contribution to provident fund and ESI"] + [inr(R(c["pl"]["emp"] * 0.071)) for c in cols])
    rows.append(["Gratuity (Note on employee benefits)"] + [inr(c["pl"]["gratuity_exp"]) for c in cols])
    rows.append(["Staff welfare expenses"] + [inr(R(c["pl"]["emp"] * 0.024)) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["pl"]["emp"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(5,))
    doc.h3("Gratuity (defined benefit, unfunded) - principal actuarial assumptions")
    dr = {"Sep26": "6.80%", "Mar26": "6.85%", "Mar25": "7.00%", "Mar24": "7.10%", "Mar23": "7.30%"}
    rows = [["Assumption"] + [f"As at {c['label']}" for c in cols],
            ["Discount rate"] + [dr.get(c["close"], "7.30%") for c in cols],
            ["Salary escalation rate"] + ["6.00%" for c in cols],
            ["Attrition rate"] + ["5.00%" for c in cols],
            ["Mortality table"] + ["IALM (2012-14) Ultimate" for c in cols],
            ["Present value of obligation (₹ lakhs)"] + [inr(R(c["bs"]["gratuity_nc"] + c["bs"]["gratuity_c"])) for c in cols]]
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))


def note_finance(doc, cols, no):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: Finance costs")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    lab = {"TL0": "Interest on term loan TL-I", "TL1": "Interest on term loan TL-II", "VEH": "Interest on vehicle loans",
           "CC": "Interest on cash credit", "UNSEC": "Interest on unsecured loan from Promoter"}
    for k, l in lab.items():
        rows.append([l] + [inr(c["pl"]["interest"][k]) for c in cols])
    rows.append(["Bank charges, processing fees and LC charges"] + [inr(c["pl"]["bank_charges"]) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["pl"]["fin"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(len(rows) - 1,))


def note_other_exp(doc, cols, no):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: Other expenses")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    for k in cols[0]["pl"]["oe_detail"]:
        rows.append([k] + [inr(c["pl"]["oe_detail"].get(k, 0.0)) for c in cols])
    rows.append(["<b>Total</b>"] + [inr(c["pl"]["oe"]) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(len(rows) - 1,))
    doc.h3("Corporate social responsibility (Section 135)")
    rows = [["Particulars"] + [c["plabel"] for c in cols],
            ["Amount required to be spent"] + [inr(c["pl"]["csr_obligation"] * (0.5 if c["p"] == "H1FY27" else 1)) for c in cols],
            ["Amount spent (promotion of education and rural health)"] + [inr(c["pl"]["csr"]) for c in cols],
            ["Shortfall"] + ["-" for c in cols]]
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))


def note_tax(doc, cols, no):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: Tax expense and deferred tax")
    rows = [["Particulars"] + [c["plabel"] for c in cols],
            ["Profit before tax"] + [inr(c["pl"]["pbt"]) for c in cols],
            ["Tax rate (Section 115BAA)"] + ["25.168%" for c in cols],
            ["Tax at the applicable rate"] + [inr(R(c["pl"]["pbt"] * I.TAX_RATE)) for c in cols],
            ["Effect of expenses not deductible (CSR)"] + [inr(R(c["pl"]["csr"] * I.TAX_RATE)) for c in cols],
            ["Rounding and other differences"] + [inr(R(c["pl"]["tax_total"] - R(c["pl"]["pbt"] * I.TAX_RATE) - R(c["pl"]["csr"] * I.TAX_RATE))) for c in cols],
            ["<b>Total tax expense</b>"] + [inr(R(c["pl"]["tax_current"] + c["pl"]["tax_deferred"])) for c in cols]]
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(6,))
    rows = [["Deferred tax liability (net)"] + [f"As at {c['label']}" for c in cols],
            ["On difference between book and tax depreciation"] + [inr(R(c["bs"]["dtl"] + R((c["bs"]["gratuity_nc"] + c["bs"]["gratuity_c"]) * I.TAX_RATE))) for c in cols],
            ["Less: on provision for gratuity (deductible on payment)"] + [inr(-R((c["bs"]["gratuity_nc"] + c["bs"]["gratuity_c"]) * I.TAX_RATE)) for c in cols],
            ["<b>Net deferred tax liability</b>"] + [inr(c["bs"]["dtl"]) for c in cols]]
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)), total_rows=(3,))


def note_eps(doc, cols, no, restated=True):
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.h2(f"Note {no}: Earnings per share")
    sh = I.SHARES_PRE_ISSUE if restated else I.SHARES_PRE_BONUS
    rows = [["Particulars"] + [c["plabel"] for c in cols],
            ["Profit for the period (₹ lakhs)"] + [inr(c["pl"]["pat"]) for c in cols],
            ["Weighted average number of equity shares" + (" (bonus adjusted)" if restated else "")] + [num(sh) for c in cols],
            ["Basic and diluted EPS (₹)"] + [inr(round(c["pl"]["pat"] * 1e5 / sh, 2)) for c in cols],
            ["Face value per share (₹)"] + ["10.00" for c in cols]]
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))


def note_rpt(doc, d, cols, no):
    doc.h2(f"Note {no}: Related party disclosures (AS 18)")
    doc.h3("(a) Names of related parties and nature of relationship")
    doc.table([["Related party", "Relationship"]] + [[a, b] for a, b in d["rpt"]["parties"]], [70, 104])
    doc.h3("(b) Transactions during the period (₹ lakhs)")
    rows = [["Nature of transaction", "Related party"] + [c["plabel"] for c in cols]]
    for (nature, party), vals in d["rpt"]["transactions"].items():
        rows.append([nature, party] + [inr(vals.get(c["p"], 0.0)) for c in cols])
    w = [174 - 30 - 22 * len(cols), 30] + [22] * len(cols)
    doc.table(rows, w, num_cols=range(2, 2 + len(cols)))
    doc.h3("(c) Balances outstanding (₹ lakhs)")
    rows = [["Nature of balance", "Related party"] + [f"As at {c['label']}" for c in cols]]
    for (nature, party), vals in d["rpt"]["balances"].items():
        rows.append([nature, party] + [inr(vals.get(c["close"], 0.0)) for c in cols])
    doc.table(rows, w, num_cols=range(2, 2 + len(cols)))
    doc.p("Personal guarantees given by Hemant Ramniklal Desai and Kavita Hemant Desai for the credit facilities from "
          "Kalindi Bank Limited (Note on borrowings) are not charged for.", "small")


def note_contingent(doc, d, cols, no):
    doc.h2(f"Note {no}: Contingent liabilities and commitments")
    rows = [["Particulars"] + [f"As at {c['label']}" for c in cols]]
    for k, v in d["contingent"].items():
        rows.append([k] + [inr(v.get(c["close"], 0.0)) for c in cols])
    commit = {"Sep26": 959.00, "Mar26": 148.20, "Mar25": 62.40, "Mar24": 18.00, "Mar23": 0.00}
    rows.append(["Capital commitments (estimated amount of contracts remaining to be executed, net of advances)"] +
                [inr(commit.get(c["close"], 0.0)) for c in cols])
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))


def note_ratios(doc, d, cols, no):
    doc.h2(f"Note {no}: Additional regulatory information - financial ratios")
    names = [("Current ratio (times)", "current_ratio", "Current assets / current liabilities"),
             ("Debt-equity ratio (times)", "debt_equity", "Total borrowings / shareholders' funds"),
             ("Debt service coverage ratio (times)", "dscr", "(PAT + depreciation + finance costs) / (finance costs + scheduled principal repayments)"),
             ("Return on equity (%)", "roe_pct", "PAT / average shareholders' funds"),
             ("Inventory turnover (times)", "inventory_turnover", "Cost of goods sold / average inventory"),
             ("Trade receivables turnover (times)", "receivables_turnover", "Revenue from operations / average trade receivables"),
             ("Trade payables turnover (times)", "payables_turnover", "Purchases and other expenses / average trade payables"),
             ("Net capital turnover (times)", "net_capital_turnover", "Revenue from operations / working capital"),
             ("Net profit ratio (%)", "net_profit_pct", "PAT / revenue from operations"),
             ("Return on capital employed (%)", "roce_pct", "(PBT + finance costs) / (net worth + total debt + deferred tax liability)")]
    rows = [["Ratio", "Formula"] + [c["plabel"] for c in cols]]
    for lab, key, f in names:
        rows.append([lab, f] + [f"{d['ratios'][c['p']][key]:.2f}" for c in cols])
    w = [40, 174 - 40 - 20 * len(cols)] + [20] * len(cols)
    doc.table(rows, w, num_cols=range(2, 2 + len(cols)))
    doc.p("Ratios for the six months ended 30 September 2026 are not annualised. Reasons for variances above 25%: the "
          "return on equity and net profit ratio improved in FY 2024-25 because of higher capacity utilisation after "
          "the solventless laminator was commissioned and a lower share of raw-material cost; the debt service coverage "
          "ratio moved with the repayment schedule of TL-II from January 2025.", "small")


# ------------------------------------------------------------------ restated financial info -----
def restated_pdf(d, path):
    a = d["advisers"]["auditor"]
    c = d["company"]
    doc = Doc(path, "Restated Financial Information", letterhead=auditor_letterhead(d),
              footer_left=f"{c['name']} - Restated Financial Information")
    cols = restated_cols(d)
    doc.title("INDEPENDENT AUDITOR'S EXAMINATION REPORT ON THE RESTATED FINANCIAL INFORMATION")
    doc.p("To,<br/>The Board of Directors,<br/>" + c["name"] + "<br/>(formerly known as " + c["former_name"] + ")<br/>" +
          c["registered_office"], "left")
    doc.space(2)
    ps = [
        f"1. We have examined the attached Restated Financial Information of {c['name']} (formerly known as "
        f"{c['former_name']}) (the 'Company'), comprising the Restated Statement of Assets and Liabilities as at "
        "30 September 2026, 31 March 2026, 31 March 2025 and 31 March 2024, the Restated Statement of Profit and Loss and "
        "the Restated Statement of Cash Flows for the six months ended 30 September 2026 and for the years ended "
        "31 March 2026, 31 March 2025 and 31 March 2024, the Summary of Significant Accounting Policies and other "
        "explanatory information (collectively, the 'Restated Financial Information'), as approved by the Board of "
        "Directors of the Company at its meeting held on 24 October 2026 for the purpose of inclusion in the Draft Red "
        "Herring Prospectus ('DRHP') prepared by the Company in connection with its proposed initial public offer of "
        "equity shares on the SME Platform of BSE Limited ('BSE SME'), prepared in terms of the requirements of:",
        "(a) Section 26 of Part I of Chapter III of the Companies Act, 2013 (the 'Act');",
        "(b) the relevant provisions of the Securities and Exchange Board of India (Issue of Capital and Disclosure "
        "Requirements) Regulations, 2018, as amended (the 'ICDR Regulations'); and",
        "(c) the Guidance Note on Reports in Company Prospectuses (Revised 2019) issued by the Institute of Chartered "
        "Accountants of India ('ICAI'), as amended (the 'Guidance Note').",
        "2. The Company's Board of Directors is responsible for the preparation of the Restated Financial Information for "
        "the purpose of inclusion in the DRHP to be filed with BSE Limited in connection with the proposed IPO. The "
        "Restated Financial Information has been prepared by the management of the Company on the basis of preparation "
        "stated in Annexure IV. The Board of Directors' responsibility includes designing, implementing and maintaining "
        "adequate internal control relevant to the preparation and presentation of the Restated Financial Information.",
        "3. We have examined such Restated Financial Information taking into consideration: (a) the terms of reference and "
        "terms of our engagement agreed with you vide our engagement letter dated 1 August 2026; (b) the Guidance Note, "
        "which also requires that we comply with the ethical requirements of the Code of Ethics issued by the ICAI; "
        "(c) concepts of test checks and materiality to obtain reasonable assurance based on verification of evidence "
        "supporting the Restated Financial Information; and (d) the requirements of Section 26 of the Act and the ICDR "
        "Regulations.",
        "4. The Restated Financial Information has been compiled by the management from: (a) the audited special purpose "
        "interim financial statements of the Company as at and for the six months ended 30 September 2026, prepared in "
        "accordance with the Accounting Standards notified under Section 133 of the Act, which have been approved by the "
        "Board of Directors at their meeting held on 24 October 2026; and (b) the audited financial statements of the "
        "Company as at and for the years ended 31 March 2026, 31 March 2025 and 31 March 2024, prepared in accordance with "
        "the Accounting Standards, which have been approved by the Board of Directors at their meetings held on "
        "2 September 2026, 1 September 2025 and 2 September 2024 respectively.",
        f"5. For the purpose of our examination, we have relied on our audit reports issued on the financial statements "
        f"for the six months ended 30 September 2026 and the years ended 31 March 2026, 31 March 2025 and 31 March 2024, "
        f"dated 24 October 2026, 2 September 2026, 1 September 2025 and 2 September 2024 respectively. {a['name']} has been "
        "the statutory auditor of the Company for all the periods presented and holds a valid peer review certificate "
        f"No. {a['peer_review_cert']} issued by the Peer Review Board of the ICAI, valid till {a['peer_review_valid_till']}.",
        "6. Based on our examination and according to the information and explanations given to us, we report that the "
        "Restated Financial Information: (a) has been prepared after incorporating adjustments for the changes in "
        "accounting policies, material errors and regrouping / reclassifications retrospectively in the financial years "
        "ended 31 March 2025 and 31 March 2024 to reflect the same accounting treatment as per the accounting policies "
        "and grouping / classifications followed as at and for the six months ended 30 September 2026; (b) does not "
        "contain any qualifications requiring adjustments; there are no qualifications in the auditor's reports on the "
        "audited financial statements for the periods presented; and (c) has been prepared in accordance with the Act, "
        "the ICDR Regulations and the Guidance Note.",
        "7. We have also examined the following other financial information relating to the Company prepared by the "
        "management and approved by the Board of Directors, proposed to be included in the DRHP: Statement of "
        "Accounting Ratios (Annexure XXXII), Capitalisation Statement (Annexure XXXIII), Statement of Tax Shelters "
        "(Annexure XXXIV) and the Statement of Related Party Transactions (Annexure XXVIII).",
        "8. The Restated Financial Information does not reflect the effects of events that occurred subsequent to the "
        "respective dates of the reports on the audited financial statements mentioned in paragraph 4 above.",
        "9. This report should not in any way be construed as a reissuance or re-dating of any of the previous audit "
        "reports issued by us, nor should it be construed as a new opinion on any of the financial statements referred to "
        "herein. We have no responsibility to update our report for events and circumstances occurring after the date of "
        "this report.",
        "10. Our report is intended solely for use of the Board of Directors for inclusion in the DRHP to be filed with "
        "BSE Limited and the Registrar of Companies, Gujarat in connection with the proposed IPO. Our report should not be "
        "used, referred to or distributed for any other purpose except with our prior consent in writing.",
    ]
    doc.ps(ps)
    auditor_sign(doc, d, "24 October 2026")
    doc.br()
    notes = {"sc": "VI", "rs": "VII", "ltb": "VIII", "dtl": "IX", "ltp": "X", "stb": "XI", "tp": "XII", "ocl": "XIII",
             "stp": "XIV", "ppe": "XV", "cwip": "XVI", "ltla": "XVII", "inv": "XVIII", "tr": "XIX", "cash": "XX",
             "stla": "XXI", "oca": "XXI", "rev": "XXII", "oi": "XXIII", "comc": "XXIV", "chg": "XXV", "emp": "XXVI",
             "fin": "XXVII", "oe": "XXVIII", "tax": "XXIX", "eps": "XXX"}
    balance_sheet(doc, cols, "ANNEXURE I - RESTATED STATEMENT OF ASSETS AND LIABILITIES", notes)
    doc.p("The above statement should be read with the significant accounting policies and notes to the Restated "
          "Financial Information appearing in Annexure IV to Annexure XXXIV.", "small")
    auditor_sign(doc, d, "24 October 2026")
    doc.br()
    profit_and_loss(doc, cols, "ANNEXURE II - RESTATED STATEMENT OF PROFIT AND LOSS", notes)
    doc.br()
    cash_flow(doc, cols, "ANNEXURE III - RESTATED STATEMENT OF CASH FLOWS")
    doc.br()
    doc.h1("ANNEXURE IV - CORPORATE INFORMATION AND SIGNIFICANT ACCOUNTING POLICIES")
    doc.h2("A. Corporate information")
    doc.p(f"{c['name']} (CIN {c['cin']}) was incorporated on {c['incorporated_on']} as '{c['former_name']}', a private "
          f"limited company under the Companies Act, 1956, with the {c['roc']}. Pursuant to a special resolution passed "
          f"at the extraordinary general meeting held on {c['conversion_egm']}, the Company was converted into a public "
          f"limited company and a fresh certificate of incorporation consequent upon conversion was issued on "
          f"{c['converted_on']}. The Company is engaged in the business of {c['business']}, at its manufacturing facility "
          f"at Sanand-II, Ahmedabad, Gujarat.")
    doc.h2("B. Significant accounting policies")
    policies(doc)
    doc.br()
    doc.h1("ANNEXURE V - STATEMENT OF ADJUSTMENTS TO AUDITED FINANCIAL STATEMENTS")
    rs = d["restatement"]
    rows = [["Particulars", "H1 FY 2026-27", "FY 2025-26", "FY 2024-25", "FY 2023-24"]]
    aud_pat = {p: d["audited"][p]["pl"]["pat"] if p in d["audited"] else d["pl"][p]["pat"] for p in ("H1FY27", "FY26", "FY25", "FY24")}
    rows.append(["Profit after tax as per audited financial statements"] + [inr(aud_pat[p]) for p in ("H1FY27", "FY26", "FY25", "FY24")])
    rows.append(["(a) Gratuity provision recognised in the year to which it relates"] + [inr(rs[p]["gratuity"]) for p in ("H1FY27", "FY26", "FY25", "FY24")])
    rows.append(["(b) Deferred tax impact of the above"] + [inr(rs[p]["deferred_tax"]) for p in ("H1FY27", "FY26", "FY25", "FY24")])
    rows.append(["<b>Profit after tax as per Restated Statement of Profit and Loss</b>"] + [inr(d["pl"][p]["pat"]) for p in ("H1FY27", "FY26", "FY25", "FY24")])
    doc.table(rows, [78, 24, 24, 24, 24], num_cols=(1, 2, 3, 4), total_rows=(4,))
    doc.p("<b>Notes on adjustments:</b> " + rs["note"])
    doc.p("<b>Reconciliation of total equity:</b> Total equity as per audited financial statements as at 31 March 2024 was "
          f"₹{inr(d['audited']['FY24']['bs']['net_worth'])} lakhs; after the adjustment above, restated total equity is "
          f"₹{inr(d['bs']['Mar24']['net_worth'])} lakhs. There is no difference as at 31 March 2025, 31 March 2026 and "
          "30 September 2026.")
    doc.p("<b>Material regrouping:</b> Appropriate regroupings have been made in the Restated Financial Information "
          "wherever required by reclassification of the corresponding items of income, expenses, assets, liabilities "
          "and cash flows to bring them in line with the groupings as per the audited special purpose interim "
          "financial statements as at and for the six months ended 30 September 2026, and the requirements of the "
          "ICDR Regulations. In particular, current maturities of long-term borrowings have been presented under "
          "short-term borrowings for all periods.")
    doc.p("<b>Auditor qualifications and emphasis of matter:</b> There are no audit qualifications in the audit reports "
          "for the periods presented which require adjustment. CARO 2020 reports for FY 2024-25 and FY 2025-26 contain "
          "a remark on delays in deposit of provident fund dues for 2 months (since regularised), which does not require "
          "any adjustment.")
    doc.br()
    doc.h1("NOTES TO THE RESTATED FINANCIAL INFORMATION")
    note_share_capital(doc, d, cols, "VI")
    note_reserves(doc, cols, "VII")
    note_borrowings(doc, d, cols, "VIII", "XI")
    doc.h2("Note IX: Deferred tax liabilities (net) - see Note XXIX")
    note_simple(doc, cols, "X", "Long-term provisions", [("Provision for gratuity (non-current)", lambda c: c["bs"]["gratuity_nc"])])
    doc.h2("Note XII: Trade payables")
    doc.p("Dues to micro and small enterprises have been determined to the extent such parties have been identified on "
          "the basis of information collected by the management. No interest is payable under Section 16 of the MSMED "
          "Act, 2006 as all MSME dues were paid within the agreed credit period not exceeding 45 days.")
    ageing_tables(doc, cols, "pay")
    note_simple(doc, cols, "XIII", "Other current liabilities", [
        ("Statutory dues payable (GST, TDS, PF, ESI)", lambda c: R(c["bs"]["ocl"] * 0.28)),
        ("Advances from customers", lambda c: R(c["bs"]["ocl"] * 0.22)),
        ("Employee benefits payable", lambda c: R(c["bs"]["ocl"] * 0.31)),
        ("Creditors for capital goods", lambda c: R(c["bs"]["ocl"] * 0.09)),
        ("Other payables", lambda c: R(c["bs"]["ocl"] - R(c["bs"]["ocl"] * 0.28) - R(c["bs"]["ocl"] * 0.22) - R(c["bs"]["ocl"] * 0.31) - R(c["bs"]["ocl"] * 0.09)))])
    note_simple(doc, cols, "XIV", "Short-term provisions", [
        ("Provision for gratuity (current)", lambda c: c["bs"]["gratuity_c"]),
        ("Provision for income tax (net of advance tax and TDS)", lambda c: c["bs"]["tax_liab"])])
    note_ppe(doc, cols, "XV")
    note_cwip(doc, cols, "XVI")
    note_simple(doc, cols, "XVII", "Long-term loans and advances (unsecured, considered good)", [
        ("Capital advances", lambda c: c["bs"]["cap_adv"]),
        ("Security deposits (including ₹5.00 lakhs with a related party)", lambda c: c["bs"]["deposits"])])
    note_simple(doc, cols, "XVIII", "Inventories (valued at lower of cost and net realisable value)", [
        ("Raw materials (including goods in transit)", lambda c: c["bs"]["rm"]),
        ("Work-in-progress", lambda c: c["bs"]["wip"]),
        ("Finished goods", lambda c: c["bs"]["fg"]),
        ("Stores, spares and packing materials", lambda c: c["bs"]["stores"])])
    doc.h2("Note XIX: Trade receivables (unsecured)")
    ageing_tables(doc, cols, "rec")
    doc.p("Disputed receivables of ₹23.86 lakhs are due from Shreeji Snacks and Namkeen, against whom the Company has filed "
          "a complaint under Section 138 of the Negotiable Instruments Act, 1881. Management expects recovery and no "
          "provision has been made.", "small")
    note_simple(doc, cols, "XX", "Cash and bank balances", [
        ("Cash on hand", lambda c: c["bs"]["cash_on_hand"]),
        ("Balances with banks in current accounts", lambda c: c["bs"]["bank_balance"]),
        ("Other bank balances - margin money deposits (under lien)", lambda c: c["bs"]["fd_lien"])])
    note_simple(doc, cols, "XXI", "Short-term loans and advances and other current assets", [
        ("Advances to suppliers", lambda c: R(c["bs"]["oca"] * 0.38)),
        ("Balances with GST authorities", lambda c: R(c["bs"]["oca"] * 0.34)),
        ("Prepaid expenses", lambda c: R(c["bs"]["oca"] * 0.08)),
        ("Loans and advances to employees", lambda c: R(c["bs"]["oca"] * 0.05)),
        ("Export incentives receivable and interest accrued", lambda c: R(c["bs"]["oca"] - R(c["bs"]["oca"] * 0.38) - R(c["bs"]["oca"] * 0.34) - R(c["bs"]["oca"] * 0.08) - R(c["bs"]["oca"] * 0.05)))])
    note_revenue(doc, cols, "XXII")
    note_other_income(doc, cols, "XXIII")
    note_materials(doc, d, cols, "XXIV", "XXV")
    note_employee(doc, cols, "XXVI")
    note_finance(doc, cols, "XXVII")
    note_other_exp(doc, cols, "XXVIII")
    note_tax(doc, cols, "XXIX")
    note_eps(doc, cols, "XXX")
    note_rpt(doc, d, cols, "XXXI")
    note_contingent(doc, d, cols, "XXXII-A")
    note_ratios(doc, d, cols, "XXXII-B")
    doc.br()
    other_financial_information(doc, d, cols)
    auditor_sign(doc, d, "24 October 2026")
    return doc.build()


def other_financial_information(doc, d, cols):
    doc.h1("ANNEXURE XXXII - STATEMENT OF ACCOUNTING RATIOS")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    for lab, key in [("Restated profit after tax (₹ lakhs)", None), ("EBITDA (₹ lakhs)", "ebitda"),
                     ("EBITDA margin (%)", "ebitda_margin_pct"), ("Basic and diluted EPS (₹)", "eps"),
                     ("Return on net worth (%)", "ronw_pct"), ("Net asset value per share (₹)", "nav_per_share"),
                     ("Net worth (₹ lakhs)", "nw")]:
        vals = []
        for c in cols:
            if key is None:
                vals.append(inr(c["pl"]["pat"]))
            elif key == "ebitda":
                vals.append(inr(c["pl"]["ebitda"]))
            elif key == "nw":
                vals.append(inr(c["bs"]["net_worth"]))
            else:
                vals.append(f"{d['ratios'][c['p']][key]:.2f}")
        rows.append([lab] + vals)
    rows.append(["Weighted average number of equity shares (bonus adjusted)"] + [num(I.SHARES_PRE_ISSUE) for c in cols])
    w = [174 - 26 * len(cols)] + [26] * len(cols)
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))
    doc.p("Notes: (1) EBITDA = profit before tax + finance costs + depreciation and amortisation - other income. "
          "(2) Return on net worth = restated profit after tax / restated net worth at the end of the period. "
          "(3) Net asset value per share = restated net worth / number of equity shares outstanding at the end of the "
          "period, adjusted for the bonus issue. (4) Figures for the six months are not annualised.", "small")
    doc.h1("ANNEXURE XXXIII - CAPITALISATION STATEMENT")
    b = d["bs"]["Sep26"]
    rows = [["Particulars", "Pre-issue as at 30 September 2026", "As adjusted for the proposed issue"],
            ["Short-term borrowings (including current maturities)", inr(b["st_borrowings"]), "[●]"],
            ["Long-term borrowings", inr(b["lt_borrowings"]), "[●]"],
            ["<b>Total borrowings (A)</b>", inr(b["total_debt"]), "[●]"],
            ["Share capital", inr(b["share_capital"]), "[●]"],
            ["Reserves and surplus", inr(b["other_equity"]), "[●]"],
            ["<b>Total shareholders' funds (B)</b>", inr(b["net_worth"]), "[●]"],
            ["Long-term borrowings / shareholders' funds (times)", f"{b['lt_borrowings'] / b['net_worth']:.2f}", "[●]"],
            ["Total borrowings / shareholders' funds (times)", f"{b['total_debt'] / b['net_worth']:.2f}", "[●]"]]
    doc.table(rows, [94, 40, 40], num_cols=(1, 2), total_rows=(3, 6))
    doc.p("The post-issue column will be completed on finalisation of the issue price.", "small")
    doc.h1("ANNEXURE XXXIV - STATEMENT OF TAX SHELTERS")
    rows = [["Particulars"] + [c["plabel"] for c in cols]]
    for lab, f in [("Restated profit before tax", lambda c: c["pl"]["pbt"]),
                   ("Tax rate (%)", None),
                   ("Tax at notional rate", lambda c: R(c["pl"]["pbt"] * I.TAX_RATE)),
                   ("Permanent differences - CSR expenditure", lambda c: c["pl"]["csr"]),
                   ("Timing difference - depreciation (book less tax)", lambda c: R(-c["pl"]["dep"] * 0.12)),
                   ("Timing difference - gratuity (provision less payment)", lambda c: R(c["pl"]["gratuity_exp"] - I.GRATUITY_PAID[c["p"]])),
                   ("Taxable income", lambda c: R(c["pl"]["pbt"] + c["pl"]["csr"] - c["pl"]["dep"] * 0.12 + c["pl"]["gratuity_exp"] - I.GRATUITY_PAID[c["p"]])),
                   ("Tax as per income tax (current tax)", lambda c: c["pl"]["tax_current"])]:
        if f is None:
            rows.append([lab] + ["25.168" for c in cols])
        else:
            rows.append([lab] + [inr(f(c)) for c in cols])
    doc.table(rows, w, num_cols=range(1, 1 + len(cols)))


# ------------------------------------------------------------------ audited financial statements ---
def audited_pdf(d, year, path):
    a = d["advisers"]["auditor"]
    c = d["company"]
    cols = audited_cols(d, year)
    fy = {"FY24": "2023-24", "FY25": "2024-25", "FY26": "2025-26"}[year]
    end = I.DATE_LABEL[I.CLOSE[year]]
    sign_date = {"FY24": "2 September 2024", "FY25": "1 September 2025", "FY26": "2 September 2026"}[year]
    name = c["former_name"] if year != "FY26" else c["former_name"]
    doc = Doc(path, f"Audited Financial Statements {fy}", letterhead=None,
              footer_left=f"{name} - Financial statements for FY {fy}")
    doc.space(30)
    doc.title(name.upper())
    doc.p(f"CIN: {c['former_cin']}", "center")
    doc.p(c["registered_office"], "center")
    doc.space(20)
    doc.title(f"AUDITED FINANCIAL STATEMENTS<br/>FOR THE YEAR ENDED {end.upper()}")
    doc.space(30)
    doc.p(f"Statutory Auditors: {a['name']}, Chartered Accountants (FRN {a['frn']})", "center")
    doc.br()
    doc.title("INDEPENDENT AUDITOR'S REPORT")
    doc.p(f"To the Members of {name}", "left")
    doc.h2("Report on the Audit of the Financial Statements")
    doc.h3("Opinion")
    doc.p(f"We have audited the accompanying financial statements of {name} (the 'Company'), which comprise the Balance "
          f"Sheet as at {end}, the Statement of Profit and Loss and the Statement of Cash Flows for the year then ended, "
          "and notes to the financial statements, including a summary of significant accounting policies and other "
          "explanatory information. In our opinion and to the best of our information and according to the explanations "
          "given to us, the aforesaid financial statements give the information required by the Companies Act, 2013 (the "
          "'Act') in the manner so required and give a true and fair view in conformity with the accounting principles "
          f"generally accepted in India, of the state of affairs of the Company as at {end}, and its profit and its cash "
          "flows for the year ended on that date.")
    doc.h3("Basis for Opinion")
    doc.p("We conducted our audit in accordance with the Standards on Auditing specified under Section 143(10) of the Act. "
          "Our responsibilities under those Standards are further described in the Auditor's Responsibilities section of "
          "our report. We are independent of the Company in accordance with the Code of Ethics issued by the Institute of "
          "Chartered Accountants of India together with the ethical requirements relevant to our audit, and we have "
          "fulfilled our other ethical responsibilities. We believe that the audit evidence we have obtained is "
          "sufficient and appropriate to provide a basis for our opinion.")
    if year == "FY25":
        doc.h3("Emphasis of Matter")
        doc.p("We draw attention to the note on employee benefits, which describes that the gratuity obligation was "
              "actuarially valued for the first time during the year and that the shortfall of ₹14.20 lakhs relating to "
              "the previous year has been charged to the Statement of Profit and Loss for the current year. Our opinion "
              "is not modified in respect of this matter.")
    doc.h3("Information Other than the Financial Statements and Auditor's Report Thereon")
    doc.p("The Company's Board of Directors is responsible for the other information, which comprises the Board's Report "
          "including annexures. Our opinion on the financial statements does not cover the other information and we do "
          "not express any form of assurance conclusion thereon. We have nothing to report in this regard.")
    doc.h3("Management's Responsibility for the Financial Statements")
    doc.p("The Company's Board of Directors is responsible for the matters stated in Section 134(5) of the Act with respect "
          "to the preparation of these financial statements that give a true and fair view of the financial position, "
          "financial performance and cash flows of the Company in accordance with the Accounting Standards specified "
          "under Section 133 of the Act. This responsibility also includes maintenance of adequate accounting records, "
          "selection and application of appropriate accounting policies, making judgements and estimates that are "
          "reasonable and prudent, and design, implementation and maintenance of adequate internal financial controls.")
    doc.h3("Auditor's Responsibilities for the Audit of the Financial Statements")
    doc.p("Our objectives are to obtain reasonable assurance about whether the financial statements as a whole are free "
          "from material misstatement, whether due to fraud or error, and to issue an auditor's report that includes our "
          "opinion. Reasonable assurance is a high level of assurance, but is not a guarantee that an audit conducted in "
          "accordance with SAs will always detect a material misstatement when it exists. As part of an audit, we "
          "exercise professional judgment and maintain professional skepticism throughout the audit; identify and "
          "assess the risks of material misstatement; obtain an understanding of internal financial controls relevant "
          "to the audit; evaluate the appropriateness of accounting policies used; conclude on the appropriateness of "
          "management's use of the going concern basis of accounting; and evaluate the overall presentation, structure "
          "and content of the financial statements.")
    doc.h2("Report on Other Legal and Regulatory Requirements")
    doc.p("1. As required by the Companies (Auditor's Report) Order, 2020 ('CARO 2020') issued by the Central Government "
          "in terms of Section 143(11) of the Act, we give in 'Annexure A' a statement on the matters specified in "
          "paragraphs 3 and 4 of the Order.")
    doc.p("2. As required by Section 143(3) of the Act, we report that: (a) we have sought and obtained all the information "
          "and explanations which to the best of our knowledge and belief were necessary for the purposes of our audit; "
          "(b) in our opinion, proper books of account as required by law have been kept by the Company; (c) the Balance "
          "Sheet, the Statement of Profit and Loss and the Statement of Cash Flows dealt with by this report are in "
          "agreement with the books of account; (d) in our opinion, the aforesaid financial statements comply with the "
          "Accounting Standards specified under Section 133 of the Act; (e) on the basis of the written representations "
          "received from the directors, none of the directors is disqualified from being appointed as a director in terms "
          "of Section 164(2) of the Act; (f) with respect to the adequacy of the internal financial controls with "
          "reference to financial statements and the operating effectiveness of such controls, refer to our separate "
          "report in 'Annexure B'; (g) the Company has not paid or provided for managerial remuneration in excess of the "
          "limits of Section 197 read with Schedule V of the Act; (h) the Company has disclosed the impact of pending "
          "litigations on its financial position in its financial statements; the Company did not have any long-term "
          "contracts including derivative contracts for which there were any material foreseeable losses; there were no "
          "amounts required to be transferred to the Investor Education and Protection Fund; the Company has not declared "
          "or paid any dividend during the year; and the accounting software used by the Company has a feature of "
          "recording audit trail (edit log) which has operated throughout the year for all relevant transactions.")
    auditor_sign(doc, d, sign_date, udin_seq={"FY24": "11", "FY25": "12", "FY26": "13"}[year])
    doc.br()
    doc.h1("ANNEXURE A TO THE INDEPENDENT AUDITOR'S REPORT (CARO 2020)")
    caro = [
        "(i) (a) The Company has maintained proper records showing full particulars, including quantitative details and "
        "situation of property, plant and equipment. The Company does not have intangible assets. (b) The property, plant "
        "and equipment were physically verified by the management during the year under a phased programme; no material "
        "discrepancies were noticed. (c) The title deeds of immovable properties are held in the name of the Company, "
        "the leasehold land being held under a lease deed executed by GIDC. (d) The Company has not revalued its property, "
        "plant and equipment. (e) No proceedings have been initiated against the Company under the Benami Transactions "
        "(Prohibition) Act, 1988.",
        "(ii) (a) Physical verification of inventory has been conducted at reasonable intervals by the management; no "
        "discrepancies of 10% or more in the aggregate for each class of inventory were noticed. (b) The Company has been "
        "sanctioned working capital limits in excess of ₹5 crore, in aggregate, from a bank on the basis of security of "
        "current assets; the quarterly returns filed by the Company with the bank are in agreement with the books of "
        "account except for immaterial timing differences.",
        "(iii) The Company has not made investments in, provided guarantee or security, or granted loans or advances in the "
        "nature of loans, secured or unsecured, to companies, firms, LLPs or other parties during the year.",
        "(iv) The Company has not granted loans, made investments or provided guarantees or securities covered by "
        "Sections 185 and 186 of the Act.",
        "(v) The Company has not accepted deposits or amounts deemed to be deposits within the meaning of Sections 73 to 76 "
        "of the Act.",
        "(vi) We have broadly reviewed the cost records maintained by the Company pursuant to the rules made by the "
        "Central Government for the maintenance of cost records under Section 148(1) of the Act and are of the opinion "
        "that prima facie the prescribed accounts and records have been made and maintained.",
        "(vii) (a) The Company has generally been regular in depositing undisputed statutory dues including goods and "
        "services tax, provident fund, employees' state insurance and income tax with the appropriate authorities, "
        + ("except for delays of up to 34 days in depositing provident fund contributions for two months, which have since "
           "been deposited with interest. " if year in ("FY25", "FY26") else "") +
        "No undisputed amounts were outstanding for more than six months from the date they became payable. (b) Dues "
        "that have not been deposited on account of disputes: " +
        ("Goods and Services Tax, FY 2021-22, ₹18.62 lakhs, pending before the Joint Commissioner (Appeals), Ahmedabad."
         if year == "FY26" else "None."),
        "(viii) There were no transactions relating to previously unrecorded income that were surrendered or disclosed as "
        "income in the tax assessments under the Income-tax Act, 1961.",
        "(ix) The Company has not defaulted in the repayment of loans or other borrowings or in the payment of interest "
        "thereon to any lender. Term loans were applied for the purposes for which they were obtained. Funds raised on a "
        "short-term basis have not been utilised for long-term purposes.",
        "(x) The Company has not raised moneys by way of initial public offer or further public offer during the year. "
        "The Company has not made any preferential allotment or private placement of shares or convertible debentures "
        "during the year.",
        "(xi) No fraud by the Company or on the Company has been noticed or reported during the year. No whistle-blower "
        "complaints were received during the year.",
        "(xii) The Company is not a Nidhi company.",
        "(xiii) Transactions with related parties are in compliance with Sections 177 and 188 of the Act where applicable "
        "and the details have been disclosed in the financial statements as required by AS 18.",
        "(xiv) In our opinion, the Company has an internal audit system commensurate with the size and nature of its "
        "business, carried out by an external firm of chartered accountants.",
        "(xv) The Company has not entered into non-cash transactions with directors or persons connected with them.",
        "(xvi) The Company is not required to be registered under Section 45-IA of the Reserve Bank of India Act, 1934.",
        "(xvii) The Company has not incurred cash losses in the current or the immediately preceding financial year.",
        "(xviii) There has been no resignation of the statutory auditors during the year.",
        "(xix) On the basis of the financial ratios, ageing and expected dates of realisation of financial assets and "
        "payment of financial liabilities, no material uncertainty exists as on the date of the audit report that the "
        "Company is not capable of meeting its liabilities existing at the date of the balance sheet as and when they "
        "fall due within a period of one year from the balance sheet date.",
        "(xx) " + ("The Company has spent the amount required under Section 135 of the Act; there is no unspent amount."
                   if d["pl"][year]["csr"] > 0 else "The provisions of Section 135 of the Act were not applicable to the Company for the year."),
        "(xxi) The reporting under clause (xxi) is not applicable in respect of standalone financial statements.",
    ]
    doc.ps(caro)
    auditor_sign(doc, d, sign_date, udin_seq={"FY24": "11", "FY25": "12", "FY26": "13"}[year])
    doc.br()
    doc.h1("ANNEXURE B - REPORT ON INTERNAL FINANCIAL CONTROLS WITH REFERENCE TO FINANCIAL STATEMENTS")
    doc.p("We have audited the internal financial controls with reference to financial statements of the Company as at "
          f"{end} in conjunction with our audit of the financial statements of the Company for the year ended on that "
          "date. In our opinion, the Company has, in all material respects, adequate internal financial controls with "
          "reference to financial statements and such controls were operating effectively as at " + end + ", based on the "
          "internal control with reference to financial statements criteria established by the Company considering the "
          "essential components of internal control stated in the Guidance Note on Audit of Internal Financial Controls "
          "over Financial Reporting issued by the Institute of Chartered Accountants of India.")
    auditor_sign(doc, d, sign_date, udin_seq={"FY24": "11", "FY25": "12", "FY26": "13"}[year])
    doc.br()
    notes = {"sc": "2", "rs": "3", "ltb": "4", "dtl": "5", "ltp": "6", "stb": "7", "tp": "8", "ocl": "9", "stp": "10",
             "ppe": "11", "cwip": "12", "ltla": "13", "inv": "14", "tr": "15", "cash": "16", "stla": "17", "oca": "17",
             "rev": "18", "oi": "19", "comc": "20", "chg": "21", "emp": "22", "fin": "23", "oe": "24", "tax": "25", "eps": "26"}
    balance_sheet(doc, cols, f"BALANCE SHEET AS AT {end.upper()}", notes)
    _board_sign(doc, d, sign_date)
    doc.br()
    profit_and_loss(doc, cols, f"STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED {end.upper()}", notes, restated=False)
    _board_sign(doc, d, sign_date)
    doc.br()
    cash_flow(doc, cols, f"STATEMENT OF CASH FLOWS FOR THE YEAR ENDED {end.upper()}")
    doc.br()
    doc.h1("NOTES TO THE FINANCIAL STATEMENTS")
    doc.h2("Note 1: Corporate information and significant accounting policies")
    doc.p(f"{name} is a private limited company incorporated on {c['incorporated_on']} and domiciled in India, engaged in "
          f"the business of {c['business']}.")
    policies(doc)
    note_share_capital_audited(doc, d, cols)
    note_reserves_audited(doc, cols)
    note_borrowings(doc, d, cols, "4", "7")
    note_simple(doc, cols, "6", "Long-term provisions", [("Provision for gratuity (non-current)", lambda x: x["bs"]["gratuity_nc"])])
    doc.h2("Note 8: Trade payables")
    ageing_tables(doc, cols, "pay")
    note_simple(doc, cols, "9", "Other current liabilities", [
        ("Statutory dues payable", lambda x: R(x["bs"]["ocl"] * 0.28)), ("Advances from customers", lambda x: R(x["bs"]["ocl"] * 0.22)),
        ("Employee benefits payable", lambda x: R(x["bs"]["ocl"] * 0.31)),
        ("Other payables", lambda x: R(x["bs"]["ocl"] - R(x["bs"]["ocl"] * 0.28) - R(x["bs"]["ocl"] * 0.22) - R(x["bs"]["ocl"] * 0.31)))])
    note_simple(doc, cols, "10", "Short-term provisions", [("Provision for gratuity (current)", lambda x: x["bs"]["gratuity_c"]),
                                                          ("Provision for income tax (net)", lambda x: x["bs"]["tax_liab"])])
    note_ppe(doc, cols[:1], "11")
    note_cwip(doc, cols, "12")
    note_simple(doc, cols, "13", "Long-term loans and advances", [("Capital advances", lambda x: x["bs"]["cap_adv"]),
                                                                 ("Security deposits", lambda x: x["bs"]["deposits"])])
    note_simple(doc, cols, "14", "Inventories", [("Raw materials", lambda x: x["bs"]["rm"]), ("Work-in-progress", lambda x: x["bs"]["wip"]),
                                                ("Finished goods", lambda x: x["bs"]["fg"]), ("Stores and spares", lambda x: x["bs"]["stores"])])
    doc.h2("Note 15: Trade receivables")
    ageing_tables(doc, cols, "rec")
    note_simple(doc, cols, "16", "Cash and bank balances", [("Cash on hand", lambda x: x["bs"]["cash_on_hand"]),
                                                           ("Balances with banks", lambda x: x["bs"]["bank_balance"]),
                                                           ("Margin money deposits", lambda x: x["bs"]["fd_lien"])])
    note_revenue(doc, cols, "18")
    note_other_income(doc, cols, "19")
    note_materials(doc, d, cols, "20", "21")
    note_employee(doc, cols, "22")
    note_finance(doc, cols, "23")
    note_other_exp(doc, cols, "24")
    note_tax(doc, cols, "25")
    note_eps(doc, cols, "26", restated=False)
    note_rpt(doc, d, cols, "27")
    note_contingent(doc, d, cols, "28")
    note_ratios(doc, d, cols, "29")
    doc.h2("Note 30: Events after the reporting period")
    if year == "FY26":
        doc.p("The shareholders approved the conversion of the Company into a public limited company on 10 June 2026; the "
              "fresh certificate of incorporation was issued on 2 July 2026. No adjustment is required in these financial "
              "statements.")
    else:
        doc.p("There are no events after the reporting period that require adjustment or disclosure.")
    doc.h2("Note 31: Previous year figures")
    doc.p("Previous year figures have been regrouped and reclassified wherever necessary to conform to the current year's "
          "classification.")
    _board_sign(doc, d, sign_date)
    return doc.build()


def note_share_capital_audited(doc, d, cols):
    doc.h2("Note 2: Share capital")
    rows = [["Particulars"] + [f"As at {c['label']}" for c in cols],
            ["Authorised: 25,00,000 equity shares of ₹10 each"] + [inr(250.00) for c in cols],
            ["Issued, subscribed and paid up: 20,00,000 equity shares of ₹10 each fully paid"] + [inr(200.00) for c in cols]]
    doc.table(rows, [174 - 52, 26, 26], num_cols=(1, 2))
    h = d["holdings"]["pre_bonus"]
    rows = [["Shareholders holding more than 5%", "Number of shares", "% holding"]]
    for n in ("Hemant Ramniklal Desai", "Kavita Hemant Desai", "Parth Hemant Desai"):
        rows.append([n, num(h[n]), pct(100 * h[n] / I.SHARES_PRE_BONUS)])
    doc.table(rows, [100, 40, 34], num_cols=(1, 2))


def note_reserves_audited(doc, cols):
    doc.h2("Note 3: Reserves and surplus")
    rows = [["Particulars"] + [f"As at {c['label']}" for c in cols],
            ["Securities premium"] + [inr(c["bs"]["securities_premium"]) for c in cols],
            ["Surplus in the Statement of Profit and Loss - opening"] + [inr(R(c["bs"]["retained_earnings"] - c["pl"]["pat"])) for c in cols],
            ["Add: profit for the year"] + [inr(c["pl"]["pat"]) for c in cols],
            ["Surplus - closing"] + [inr(c["bs"]["retained_earnings"]) for c in cols],
            ["<b>Total</b>"] + [inr(c["bs"]["other_equity"]) for c in cols]]
    doc.table(rows, [174 - 52, 26, 26], num_cols=(1, 2), total_rows=(5,))


def _board_sign(doc, d, date):
    a = d["advisers"]["auditor"]
    doc.signature(["For and on behalf of the Board of Directors", "", "Sd/-  Hemant Ramniklal Desai, Managing Director (DIN 02718465)",
                   "Sd/-  Kavita Hemant Desai, Director (DIN 02718472)", "Sd/-  Sanjay Prakash Khatri, Chief Financial Officer"],
                  left=[f"As per our report of even date", f"For {a['name']}, Chartered Accountants (FRN {a['frn']})",
                        f"Sd/- {a['partner']}, Partner (M. No. {a['membership']})", f"Place: Ahmedabad", f"Date: {date}"])


# ------------------------------------------------------------------ certificates ---------------
def kpi_certificate(d, path):
    c = d["company"]
    doc = Doc(path, "KPI Certificate", letterhead=auditor_letterhead(d))
    doc.p("Date: 26 October 2026", "right")
    doc.p(f"To,<br/>The Board of Directors, {c['name']}<br/>{c['registered_office']}<br/><br/>"
          f"{d['advisers']['brlm']['name']} (the 'Book Running Lead Manager')<br/>{d['advisers']['brlm']['address']}", "left")
    doc.space(2)
    doc.p("<b>Re: Certificate on Key Performance Indicators ('KPIs') in connection with the proposed initial public offer of "
          f"equity shares of face value ₹10 each of {c['name']} on the SME Platform of BSE Limited</b>")
    doc.p("1. We, N K Bhatt & Co., Chartered Accountants, the statutory auditors of the Company, have been requested by the "
          "Company to certify the KPIs set out below, which have been identified by the management and approved by the "
          "Audit Committee of the Company by its resolution dated 25 October 2026, for disclosure in the Draft Red Herring "
          "Prospectus ('DRHP') in the chapter 'Basis for Offer Price'.")
    doc.p("2. The financial KPIs have been computed from the Restated Financial Information examined by us (report dated "
          "24 October 2026). The operational KPIs have been verified with the production registers, sales registers and "
          "customer master maintained by the Company on a test-check basis.")
    rows = [["KPI", "H1 FY 2026-27", "FY 2025-26", "FY 2024-25", "FY 2023-24"]]
    for k in d["kpi"]["FY26"]:
        vals = []
        for p in ("H1FY27", "FY26", "FY25", "FY24"):
            v = d["kpi"][p][k]
            vals.append("-" if v is None else (num(v) if isinstance(v, int) else (inr(v) if "lakhs" in k else f"{v:.2f}")))
        rows.append([k] + vals)
    doc.table(rows, [70, 26, 26, 26, 26], num_cols=(1, 2, 3, 4))
    doc.p("Notes: (a) Figures for the six months ended 30 September 2026 are not annualised. (b) Capacity utilisation = "
          "actual production of laminated output (MT) / installed lamination capacity (MT) for the period. (c) Net debt = "
          "total borrowings less cash and bank balances. (d) Growth in revenue for FY 2023-24 is computed on audited revenue "
          f"of ₹{inr(d['pl']['FY23']['revenue'])} lakhs for FY 2022-23.", "small")
    doc.p("3. The KPIs set out above are the only KPIs disclosed by the Company to its investors at any point during the "
          "three years preceding the date of the DRHP, and the Company has not disclosed any KPI to pre-IPO investors that "
          "is not included above.")
    doc.p("4. This certificate is issued for inclusion in the DRHP and for submission to BSE Limited and should not be used "
          "for any other purpose.")
    auditor_sign(doc, d, "26 October 2026", udin_seq="21")
    return doc.build()


def wc_certificate(d, path):
    c = d["company"]
    wc = d["working_capital"]
    doc = Doc(path, "Working Capital Certificate", letterhead=auditor_letterhead(d))
    doc.p("Date: 26 October 2026", "right")
    doc.p(f"To,<br/>The Board of Directors, {c['name']}<br/>{c['registered_office']}", "left")
    doc.p("<b>Re: Certificate on the basis of estimation of working capital requirements</b>")
    doc.p("We have been requested by the Company to certify the details of the actual working capital for FY 2023-24, "
          "FY 2024-25 and FY 2025-26 (on the basis of the Restated Financial Information) and the estimated working capital "
          "requirements for FY 2026-27 and FY 2027-28 as approved by the Board of Directors at its meeting held on 25 October "
          "2026. The estimates are the responsibility of the management; we have verified the arithmetical accuracy and "
          "the consistency of the assumptions with the Company's past performance.")
    keys = ["FY24", "FY25", "FY26", "FY27E", "FY28E"]
    head = ["Particulars", "FY 2023-24 (actual)", "FY 2024-25 (actual)", "FY 2025-26 (actual)", "FY 2026-27 (estimated)", "FY 2027-28 (estimated)"]
    rows = [head, ["<b>Current assets</b>", "", "", "", "", ""]]
    for item in wc["rows"]["FY24"]["ca"]:
        rows.append([item] + [inr(wc["rows"][k]["ca"][item]) for k in keys])
    rows.append(["<b>Total current assets (A)</b>"] + [inr(wc["rows"][k]["gross_ca"]) for k in keys])
    rows.append(["<b>Current liabilities</b>", "", "", "", "", ""])
    for item in wc["rows"]["FY24"]["cl"]:
        rows.append([item] + [inr(wc["rows"][k]["cl"][item]) for k in keys])
    rows.append(["<b>Total current liabilities (B)</b>"] + [inr(wc["rows"][k]["total_cl"]) for k in keys])
    rows.append(["<b>Working capital gap (A - B)</b>"] + [inr(wc["rows"][k]["wc_gap"]) for k in keys])
    rows.append(["<b>Funding pattern</b>", "", "", "", "", ""])
    for item in ["Borrowings (cash credit)", "Internal accruals / net worth", "Issue proceeds"]:
        rows.append([item] + [inr(wc["rows"][k]["funding"].get(item, 0.0)) for k in keys])
    doc.table(rows, [44, 26, 26, 26, 26, 26], num_cols=range(1, 6), total_rows=(6, 10, 11))
    doc.h3("Holding levels")
    rows = [["Particulars"] + head[1:]]
    for item, v in wc["holding"].items():
        rows.append([item] + [str(v[k]) for k in keys])
    doc.table(rows, [44, 26, 26, 26, 26, 26], num_cols=range(1, 6))
    doc.h3("Justification for holding levels (as provided by management)")
    for j in wc["justification"]:
        doc.p("&bull; " + j, "left")
    auditor_sign(doc, d, "26 October 2026", udin_seq="22")
    return doc.build()


def funds_deployed_certificate(d, path):
    c = d["company"]
    f = d["funds_deployed"]
    doc = Doc(path, "Certificate on Funds Deployed", letterhead=auditor_letterhead(d))
    doc.p("Date: 27 October 2026", "right")
    doc.p(f"To,<br/>The Board of Directors, {c['name']}<br/><br/>{d['advisers']['brlm']['name']}", "left")
    doc.p("<b>Re: Certificate on the amount deployed towards the Objects of the Issue as on " + f["as_on"] + "</b>")
    doc.p("On the basis of the books of account, bank statements and supporting documents produced before us, we certify "
          f"that the Company has deployed an amount of ₹{inr(f['amount'])} lakhs towards the Objects of the proposed Issue up "
          f"to {f['as_on']}, as set out below:")
    rows = [["Object", "Amount deployed (₹ lakhs)", "Source of funds", "Particulars"],
            ["Purchase of plant and machinery", inr(f["amount"]), f["source"], f["detail"]],
            ["<b>Total</b>", inr(f["amount"]), "", ""]]
    doc.table(rows, [44, 26, 30, 74], num_cols=(1,), total_rows=(2,))
    doc.p("The Company proposes to recoup the above amount from the Net Proceeds of the Issue. No bridge loan has been "
          "availed against the Issue proceeds.")
    auditor_sign(doc, d, "27 October 2026", udin_seq="23")
    return doc.build()


def tax_benefits_statement(d, path):
    c = d["company"]
    doc = Doc(path, "Statement of Special Tax Benefits", letterhead=auditor_letterhead(d))
    doc.p("Date: 27 October 2026", "right")
    doc.p(f"To,<br/>The Board of Directors, {c['name']}<br/><br/>{d['advisers']['brlm']['name']}", "left")
    doc.p("<b>Re: Statement of possible special tax benefits available to the Company and its shareholders</b>")
    doc.ps([
        "1. We hereby confirm that the enclosed Annexure, prepared by the Company, states the possible special tax benefits "
        "available to the Company and to its shareholders under the direct and indirect tax laws presently in force in "
        "India, including the Income-tax Act, 1961, the Central Goods and Services Tax Act, 2017, the respective State Goods "
        "and Services Tax Acts, the Customs Act, 1962, the Customs Tariff Act, 1975 and the Foreign Trade Policy 2023.",
        "2. Several of these benefits are dependent on the Company or its shareholders fulfilling the conditions prescribed "
        "under the relevant provisions of the tax laws. Hence, the ability of the Company or its shareholders to derive the "
        "special tax benefits is dependent upon their fulfilling such conditions.",
        "3. The benefits discussed in the enclosed Annexure are not exhaustive. This statement is only intended to provide "
        "general information to investors and is neither designed nor intended to be a substitute for professional tax advice.",
        "4. We do not express any opinion or provide any assurance as to whether the Company or its shareholders will continue "
        "to obtain these benefits in future, or whether the conditions prescribed for availing the benefits have been or would "
        "be met with."])
    doc.h2("ANNEXURE - STATEMENT OF POSSIBLE SPECIAL TAX BENEFITS")
    doc.h3("A. Special tax benefits available to the Company")
    doc.ps([
        "(i) Lower corporate tax rate under Section 115BAA of the Income-tax Act: the Company has opted for the concessional "
        "rate of 22% (plus surcharge of 10% and cess of 4%) from Assessment Year 2020-21, subject to not claiming specified "
        "deductions and incentives. The option, once exercised, cannot be withdrawn.",
        "(ii) Deduction under Section 80JJAA: the Company may claim a deduction of 30% of the additional employee cost incurred "
        "on new eligible employees for three assessment years, subject to the conditions prescribed (not availed so far).",
        "(iii) Export Promotion Capital Goods scheme: the Company holds an EPCG authorisation for import of capital goods at "
        "zero customs duty, subject to an export obligation of six times the duty saved over six years.",
        "(iv) RoDTEP: the Company is eligible for remission of duties and taxes on exported products at the notified rates."])
    doc.h3("B. Special tax benefits available to the shareholders")
    doc.p("There are no special tax benefits available to the shareholders of the Company.")
    auditor_sign(doc, d, "27 October 2026", udin_seq="24")
    return doc.build()
