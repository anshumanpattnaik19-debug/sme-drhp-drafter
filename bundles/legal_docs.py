"""Corporate and legal PDFs: MoA, AoA, certificates of incorporation, allotment records, leave-and-licence
agreement, bank sanction letters, GST certificate, licences, supplier quotations."""
from __future__ import annotations

import issuer as I
from common import inr, num
from pdfkit import Doc


def _co(d):
    return d["company"]


# ------------------------------------------------------------------ MoA ------------------------
def moa(d, path):
    c = _co(d)
    doc = Doc(path, "Memorandum of Association", font="Times", size=10.5, footer_left=None)
    doc.p("THE COMPANIES ACT, 2013", "center")
    doc.p("COMPANY LIMITED BY SHARES", "center")
    doc.space(2)
    doc.title("MEMORANDUM OF ASSOCIATION<br/>OF<br/>" + c["name"].upper())
    doc.p("(Altered by special resolution passed at the Extraordinary General Meeting held on 10 June 2026 on conversion "
          "into a public company, and on 1 August 2026 for increase in authorised share capital)", "center")
    doc.space(3)
    doc.p("I. The name of the Company is <b>" + c["name"].upper() + "</b>.")
    doc.p("II. The Registered Office of the Company will be situated in the State of Gujarat.")
    doc.p("III. (A) THE OBJECTS TO BE PURSUED BY THE COMPANY ON ITS INCORPORATION ARE:")
    objs = [
        "To carry on in India or elsewhere the business of manufacturers, processors, converters, printers, laminators, "
        "coaters, extruders, importers, exporters, buyers, sellers, traders and dealers of all kinds of flexible packaging "
        "materials, including printed and unprinted films, laminates of plastic, paper, aluminium foil and their "
        "combinations, pouches, bags, sachets, wrappers, sleeves, labels and roll stock, for use in food, beverages, "
        "pharmaceuticals, personal care, agro-chemicals and other industries.",
        "To carry on the business of manufacturing, blowing, extruding and co-extruding polyethylene, polypropylene and "
        "other polymer films and of rotogravure, flexographic and digital printing on such films and substrates.",
        "To set up, acquire, operate and maintain plants, machinery, laboratories and research facilities for the design, "
        "development, testing and certification of packaging structures, and to provide packaging design, pre-press, "
        "cylinder engraving and consultancy services.",
    ]
    for i, o in enumerate(objs, 1):
        doc.p(f"{i}. {o}")
    doc.p("III. (B) MATTERS WHICH ARE NECESSARY FOR FURTHERANCE OF THE OBJECTS SPECIFIED IN CLAUSE III(A) ARE:")
    anc = [
        "To purchase, take on lease or licence, or otherwise acquire any lands, buildings, plant, machinery and other "
        "property, movable or immovable, necessary or convenient for the business of the Company.",
        "To borrow or raise money, with or without security, including by the issue of debentures, and to secure the "
        "repayment of money borrowed by mortgage, hypothecation or charge on the whole or any part of the property of the "
        "Company, subject to the provisions of the Companies Act, 2013.",
        "To enter into partnerships, joint ventures or arrangements for sharing of profits or technical collaboration with "
        "any person or company carrying on business similar to that of the Company.",
        "To apply for, purchase or otherwise acquire trade marks, patents, designs, licences and concessions, and to use, "
        "develop or grant licences in respect of them.",
        "To open and operate bank accounts, to draw, accept, endorse and negotiate bills of exchange, promissory notes and "
        "other negotiable instruments.",
        "To employ technical experts, consultants and staff, and to establish and support provident, gratuity and welfare "
        "funds for the benefit of employees and their dependants.",
        "To undertake corporate social responsibility activities in accordance with Section 135 of the Companies Act, 2013.",
        "To insure the property and undertaking of the Company against loss or damage.",
        "To invest the surplus funds of the Company in such manner as may be determined by the Board of Directors from time "
        "to time, subject to applicable law.",
        "To amalgamate, merge or enter into any arrangement with any company having objects similar to those of the Company.",
        "To distribute among the members in specie any property of the Company in the event of winding up, subject to law.",
        "To do all such other things as are incidental or conducive to the attainment of the above objects or any of them.",
    ]
    for i, o in enumerate(anc, 1):
        doc.p(f"{i}. {o}")
    doc.p("IV. The liability of the members is limited, and this liability is limited to the amount unpaid, if any, on the "
          "shares held by them.")
    doc.p("V. The Authorised Share Capital of the Company is ₹15,00,00,000 (Rupees Fifteen Crore only) divided into "
          "1,50,00,000 (One Crore Fifty Lakh) Equity Shares of ₹10 (Rupees Ten) each, with power to increase or reduce the "
          "capital and to divide the shares into several classes in accordance with the Articles of Association and the "
          "Companies Act, 2013.")
    doc.p("VI. We, the several persons whose names and addresses are subscribed, are desirous of being formed into a "
          "company in pursuance of this Memorandum of Association, and we respectively agree to take the number of shares "
          "in the capital of the Company set opposite our respective names:")
    rows = [["Name, address, description and occupation of subscriber", "Number of equity shares taken", "Signature",
             "Witness"],
            ["Hemant Ramniklal Desai, S/o Ramniklal Desai, Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad. Occupation: Business",
             "5,000", "Sd/-", "Witness to both subscribers: CA Pravin M. Shah, Ahmedabad (M. No. 0412X8)"],
            ["Kavita Hemant Desai, W/o Hemant Desai, Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad. Occupation: Business",
             "5,000", "Sd/-", ""],
            ["<b>Total</b>", "<b>10,000</b>", "", ""]]
    doc.table(rows, [80, 28, 20, 46], num_cols=(1,))
    doc.p("Place: Ahmedabad &nbsp;&nbsp;&nbsp; Date: 8 August 2012", "left")
    return doc.build()


# ------------------------------------------------------------------ AoA ------------------------
AOA_PARTS = [
    ("PRELIMINARY", [
        ("Table F not to apply", "The regulations contained in Table 'F' in Schedule I to the Companies Act, 2013 shall not "
         "apply to the Company, except in so far as the same are repeated, contained or expressly made applicable in these "
         "Articles or by the Act."),
        ("Interpretation", "In these Articles, unless the context otherwise requires: 'the Act' means the Companies Act, 2013 "
         "and the rules made thereunder, including any statutory modification or re-enactment for the time being in force; "
         "'the Board' means the Board of Directors of the Company; 'the Company' means " + "Ashtavira Flexipak Limited; "
         "'Depository' has the meaning assigned to it in the Depositories Act, 1996; 'SEBI' means the Securities and Exchange "
         "Board of India; 'Stock Exchange' means any recognised stock exchange on which the shares of the Company are listed; "
         "'Seal' means the common seal, if any, of the Company. Words importing the singular include the plural and vice versa."),
        ("Public company", "The Company is a public company within the meaning of Section 2(71) of the Act."),
    ]),
    ("SHARE CAPITAL AND VARIATION OF RIGHTS", [
        ("Authorised capital", "The Authorised Share Capital of the Company shall be such amount as is stated in Clause V of "
         "the Memorandum of Association, with power to increase, reduce, consolidate, sub-divide or reclassify the capital."),
        ("Shares under control of the Board", "Subject to the provisions of the Act and these Articles, the shares in the "
         "capital of the Company shall be under the control of the Board, who may issue, allot or otherwise dispose of the "
         "same to such persons, in such proportion, on such terms and at such times as the Board may think fit."),
        ("Further issue of shares", "Where at any time the Company proposes to increase its subscribed capital by the issue "
         "of further shares, such shares shall be offered in accordance with Section 62 of the Act, including to existing "
         "members in proportion to their holding, to employees under a scheme of employee stock option, or to any persons "
         "if authorised by a special resolution."),
        ("Dematerialisation", "Notwithstanding anything contained in these Articles, the Company shall be entitled to "
         "dematerialise its securities and to offer securities in a dematerialised form pursuant to the Depositories Act, "
         "1996. Every person subscribing to securities offered by the Company shall have the option to receive security "
         "certificates or to hold the securities with a Depository, subject to the requirements of SEBI and the Stock "
         "Exchanges, which may require securities to be issued only in dematerialised form."),
        ("Share certificates", "Every person whose name is entered as a member in the register of members shall be "
         "entitled to receive within two months after allotment or within one month after the application for "
         "registration of transfer, one or more certificates in marketable lots, under the seal, if any, or signed by two "
         "directors and the company secretary or a person authorised by the Board."),
        ("Variation of rights", "If at any time the share capital is divided into different classes of shares, the rights "
         "attached to any class may, subject to Section 48 of the Act, be varied with the consent in writing of the holders "
         "of not less than three-fourths of the issued shares of that class, or with the sanction of a special resolution "
         "passed at a separate meeting of the holders of the shares of that class."),
        ("Commission and brokerage", "The Company may exercise the powers of paying commissions conferred by Section 40(6) "
         "of the Act, provided that the rate per cent or the amount of the commission paid shall be disclosed in the manner "
         "required by the Act and the rules made thereunder."),
        ("Preference shares", "Subject to Section 55 of the Act, any preference shares may, with the sanction of a special "
         "resolution, be issued on the terms that they are to be redeemed on such terms and in such manner as the Company "
         "may determine before the issue of the shares."),
    ]),
    ("LIEN", [
        ("Company's lien", "The Company shall have a first and paramount lien on every share (not being a fully paid share) "
         "for all monies, whether presently payable or not, called or payable at a fixed time in respect of that share. "
         "Fully paid shares shall be free from all lien."),
        ("Enforcement of lien by sale", "The Company may sell, in such manner as the Board thinks fit, any shares on which "
         "the Company has a lien, provided that no sale shall be made unless a sum in respect of which the lien exists is "
         "presently payable and a notice in writing of fourteen days has been given to the registered holder."),
        ("Application of sale proceeds", "The proceeds of the sale shall be received by the Company and applied in payment "
         "of such part of the amount in respect of which the lien exists as is presently payable, and the residue, if any, "
         "shall be paid to the person entitled to the shares at the date of the sale."),
    ]),
    ("CALLS ON SHARES", [
        ("Calls", "The Board may, from time to time, make calls upon the members in respect of any monies unpaid on their "
         "shares, provided that no call shall exceed one-fourth of the nominal value of the share or be payable at less than "
         "one month from the date fixed for the payment of the last preceding call."),
        ("Interest on calls", "If a sum called in respect of a share is not paid before or on the day appointed for payment, "
         "the person from whom the sum is due shall pay interest at such rate not exceeding ten per cent per annum as the "
         "Board may determine."),
        ("Payment in advance", "The Board may, if it thinks fit, receive from any member willing to advance the same, all or "
         "any part of the monies uncalled and unpaid upon any shares held by him."),
    ]),
    ("TRANSFER AND TRANSMISSION OF SHARES", [
        ("Instrument of transfer", "The instrument of transfer of any share shall be in the form prescribed under Section 56 "
         "of the Act and shall be executed by or on behalf of both the transferor and transferee. Transfers of securities "
         "held in a depository shall be governed by the Depositories Act, 1996."),
        ("Board's right to decline", "Subject to Section 58 of the Act and the listing regulations, the Board may decline to "
         "register the transfer of a share, not being a fully paid share, to a person of whom they do not approve, or any "
         "transfer of shares on which the Company has a lien."),
        ("Transmission", "On the death of a member, the survivor or survivors where the member was a joint holder, and his "
         "nominee or legal representatives where he was a sole holder, shall be the only persons recognised by the Company "
         "as having any title to his interest in the shares."),
        ("Nomination", "Every holder of securities may, at any time, nominate in the prescribed manner a person to whom his "
         "securities shall vest in the event of his death, in accordance with Section 72 of the Act."),
    ]),
    ("FORFEITURE OF SHARES", [
        ("Notice", "If a member fails to pay any call or instalment of a call on the day appointed for payment, the Board may "
         "serve a notice requiring payment of so much of the call as is unpaid together with any interest accrued."),
        ("Forfeiture", "If the requirements of any such notice are not complied with, any share in respect of which the "
         "notice has been given may be forfeited by a resolution of the Board to that effect."),
        ("Effect of forfeiture", "A person whose shares have been forfeited shall cease to be a member in respect of the "
         "forfeited shares but shall remain liable to pay all monies which were presently payable by him in respect of the shares."),
    ]),
    ("ALTERATION OF CAPITAL AND BUY-BACK", [
        ("Alteration", "The Company may, by ordinary resolution, increase its share capital, consolidate and divide its share "
         "capital into shares of larger amount, sub-divide its shares, convert fully paid-up shares into stock, and cancel "
         "shares which have not been taken or agreed to be taken by any person."),
        ("Reduction of capital", "The Company may, by special resolution, reduce its share capital and any capital redemption "
         "reserve account or securities premium account in any manner and with any incident authorised and consent required by law."),
        ("Buy-back", "Notwithstanding anything contained in these Articles but subject to Sections 68 to 70 of the Act and the "
         "applicable SEBI regulations, the Company may purchase its own shares or other specified securities."),
        ("Capitalisation of profits", "The Company in general meeting may, upon the recommendation of the Board, resolve to "
         "capitalise any part of the amount standing to the credit of any of the free reserves, the securities premium "
         "account or the capital redemption reserve account, and to apply the same in paying up in full unissued shares to "
         "be allotted as fully paid bonus shares to the members in the proportion in which they would be entitled to dividend."),
    ]),
    ("GENERAL MEETINGS", [
        ("Annual general meeting", "The Company shall in each year hold a general meeting as its annual general meeting in "
         "accordance with Section 96 of the Act."),
        ("Extraordinary general meeting", "The Board may, whenever it thinks fit, call an extraordinary general meeting, and "
         "shall do so on the requisition of members in accordance with Section 100 of the Act."),
        ("Notice", "A general meeting may be called by giving not less than clear twenty-one days' notice in writing or "
         "through electronic mode, or at shorter notice with the consent of the requisite majority of members."),
        ("Quorum", "The quorum for a general meeting shall be as provided in Section 103 of the Act."),
        ("Chairperson", "The chairperson, if any, of the Board shall preside as chairperson at every general meeting of the Company."),
        ("Meetings through electronic means", "Members may participate in general meetings through video conferencing or "
         "other audio-visual means as permitted under the Act and circulars issued thereunder."),
        ("Postal ballot", "The Company may pass resolutions by postal ballot and shall do so for matters required to be "
         "transacted only by postal ballot under the Act."),
    ]),
    ("VOTING RIGHTS", [
        ("Votes of members", "Subject to any rights or restrictions attached to any class of shares, on a show of hands "
         "every member present in person shall have one vote, and on a poll or e-voting the voting rights of members shall "
         "be in proportion to their share in the paid-up equity share capital."),
        ("E-voting", "The Company shall provide its members the facility to exercise their right to vote by electronic means "
         "where required by the Act or the listing regulations."),
        ("Proxies", "Any member entitled to attend and vote at a meeting may appoint another person as a proxy to attend and "
         "vote instead of himself, in the form prescribed under Section 105 of the Act."),
        ("Restriction", "No member shall be entitled to vote at any general meeting unless all calls or other sums presently "
         "payable by him in respect of shares in the Company have been paid."),
    ]),
    ("BOARD OF DIRECTORS", [
        ("Number of directors", "Unless otherwise determined by a special resolution, the number of directors shall not be "
         "less than three and not more than fifteen. The first directors of the Company were Hemant Ramniklal Desai and Kavita "
         "Hemant Desai."),
        ("Independent and women directors", "The Board shall have such number of independent directors and at least one woman "
         "director as required under the Act and the listing regulations, as applicable."),
        ("Additional directors", "The Board may appoint an additional director who shall hold office up to the date of the "
         "next annual general meeting, subject to Section 161 of the Act."),
        ("Remuneration", "The remuneration of directors shall be determined in accordance with Section 197 and Schedule V of "
         "the Act. Independent directors may receive sitting fees within the limits prescribed under the Act."),
        ("Retirement by rotation", "Not less than two-thirds of the total number of directors, excluding independent directors, "
         "shall be persons whose period of office is liable to determination by retirement by rotation."),
        ("Borrowing powers", "Subject to Section 179 and Section 180 of the Act, the Board may borrow money from time to time "
         "and secure the payment of such sums in such manner as it thinks fit, provided that borrowings in excess of the "
         "aggregate of paid-up capital, free reserves and securities premium require the consent of the Company by special resolution."),
    ]),
    ("PROCEEDINGS OF THE BOARD", [
        ("Meetings", "The Board shall meet at least four times a year with a maximum gap of one hundred and twenty days "
         "between two meetings. Directors may participate through video conferencing or other audio-visual means."),
        ("Quorum", "The quorum for a meeting of the Board shall be one-third of its total strength or two directors, whichever "
         "is higher, as provided in Section 174 of the Act."),
        ("Committees", "The Board may delegate any of its powers to committees consisting of such member or members of its "
         "body as it thinks fit, including the Audit Committee, the Nomination and Remuneration Committee, the Stakeholders' "
         "Relationship Committee and the Corporate Social Responsibility Committee."),
        ("Resolution by circulation", "A resolution in writing, circulated in draft together with the necessary papers to all "
         "directors and approved by a majority of them, shall be as valid as a resolution passed at a meeting of the Board."),
    ]),
    ("MANAGING DIRECTOR, WHOLE-TIME DIRECTORS AND KEY MANAGERIAL PERSONNEL", [
        ("Appointment", "Subject to Sections 196, 197 and 203 of the Act, the Board may appoint one or more of its members as "
         "Managing Director or Whole-time Director for a term not exceeding five years at a time, and may appoint a Chief "
         "Executive Officer, Chief Financial Officer and Company Secretary."),
        ("Chairperson and Managing Director", "The same individual may be appointed as the chairperson of the Company as well "
         "as the managing director, subject to the applicable provisions of the Act and the listing regulations."),
    ]),
    ("THE SEAL", [
        ("Seal", "The Board shall provide for the safe custody of the seal, if any. The seal shall not be affixed to any "
         "instrument except by the authority of a resolution of the Board and in the presence of at least one director or "
         "the company secretary."),
    ]),
    ("DIVIDENDS AND RESERVES", [
        ("Declaration", "The Company in general meeting may declare dividends, but no dividend shall exceed the amount "
         "recommended by the Board. The Board may pay interim dividends as appear to it to be justified by the profits of the Company."),
        ("Reserves", "The Board may, before recommending any dividend, set aside out of the profits of the Company such sums "
         "as it thinks fit as a reserve or reserves applicable for any purpose to which the profits may be properly applied."),
        ("Unpaid dividend", "Any dividend unpaid or unclaimed within thirty days of declaration shall be transferred to an "
         "unpaid dividend account and dealt with in accordance with Sections 124 and 125 of the Act."),
    ]),
    ("ACCOUNTS, AUDIT AND DOCUMENTS", [
        ("Books of account", "The Company shall keep at its registered office proper books of account and other relevant "
         "books and papers and financial statements for every financial year as required by Section 128 of the Act."),
        ("Inspection by members", "No member (not being a director) shall have any right of inspecting any account or book or "
         "document of the Company except as conferred by law or authorised by the Board or by the Company in general meeting."),
        ("Audit", "The accounts of the Company shall be audited annually by a statutory auditor appointed in accordance with "
         "Section 139 of the Act."),
    ]),
    ("WINDING UP AND INDEMNITY", [
        ("Winding up", "Subject to the provisions of Chapter XX of the Act and the Insolvency and Bankruptcy Code, 2016, if the "
         "Company shall be wound up, the liquidator may, with the sanction of a special resolution, divide amongst the members, "
         "in specie or kind, the whole or any part of the assets of the Company."),
        ("Indemnity", "Every officer of the Company shall be indemnified out of the assets of the Company against any "
         "liability incurred by him in defending any proceedings, whether civil or criminal, in which judgment is given in his "
         "favour or in which he is acquitted, or in which relief is granted to him by the court or the Tribunal."),
        ("Secrecy", "Every director, manager, auditor, trustee, member of a committee, officer, servant, agent, accountant or "
         "other person employed in the business of the Company shall observe strict secrecy respecting all transactions of the "
         "Company and its customers."),
        ("General authority", "Wherever in the Act it has been provided that the Company shall have any right, privilege or "
         "authority, or that the Company could carry out any transaction only if the Company is so authorised by its articles, "
         "the Company is hereby authorised to carry out the same without the need for any specific or explicit article."),
    ]),
]


def aoa(d, path):
    c = _co(d)
    doc = Doc(path, "Articles of Association", font="Times", size=10.5)
    doc.p("THE COMPANIES ACT, 2013", "center")
    doc.p("(COMPANY LIMITED BY SHARES)", "center")
    doc.space(2)
    doc.title("ARTICLES OF ASSOCIATION<br/>OF<br/>" + c["name"].upper())
    doc.p("(New set of Articles adopted by special resolution passed at the Extraordinary General Meeting of the members held "
          "on 10 June 2026 in substitution for, and to the entire exclusion of, the earlier Articles of Association, consequent "
          "upon conversion of the Company into a public limited company)", "center")
    n = 1
    for part, arts in AOA_PARTS:
        doc.h2(part)
        for title, text in arts:
            doc.p(f"<b>{n}. {title}</b>")
            doc.p(text)
            # sub-clauses for density, as real articles have
            if len(text) > 250:
                doc.p(f"({n}A) The provisions of this Article shall apply mutatis mutandis to debentures and other securities "
                      "of the Company, to the extent applicable, and shall be read with the relevant provisions of the Act, the "
                      "rules made thereunder and any regulations issued by SEBI or the Stock Exchanges.")
            n += 1
    doc.h2("SUBSCRIBERS")
    doc.p("We, the several persons whose names and addresses are subscribed, are desirous of being formed into a company in "
          "pursuance of these Articles of Association.")
    doc.table([["Name and address of subscriber", "Signature", "Witness"],
               ["Hemant Ramniklal Desai, Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad", "Sd/-", "CA Pravin M. Shah, Ahmedabad"],
               ["Kavita Hemant Desai, Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad", "Sd/-", ""]], [90, 30, 54])
    return doc.build()


# ------------------------------------------------------------------ certificates of incorporation ---
def coi(d, path, fresh=False):
    c = _co(d)
    doc = Doc(path, "Certificate of Incorporation", font="Times", size=11, page_numbers=False)
    doc.space(8)
    doc.p("GOVERNMENT OF INDIA", "center")
    doc.p("MINISTRY OF CORPORATE AFFAIRS", "center")
    doc.p("Registrar of Companies, Gujarat, Dadra and Nagar Haveli" if not fresh else "Central Processing Centre", "center")
    doc.space(4)
    if not fresh:
        doc.title("Certificate of Incorporation")
        doc.p(f"Corporate Identity Number: {c['former_cin']}", "center")
        doc.space(4)
        doc.p(f"I hereby certify that <b>{c['former_name'].upper()}</b> is this day incorporated under the Companies Act, "
              "1956 (No. 1 of 1956) and that the company is limited by shares.")
        doc.p(f"Given under my hand at Ahmedabad this Fourteenth day of August Two Thousand Twelve.")
    else:
        doc.title("Certificate of Incorporation pursuant to change of name<br/>(Conversion of private company into public company)")
        doc.p(f"Corporate Identity Number: {c['cin']}", "center")
        doc.space(4)
        doc.p(f"I hereby certify that the name of the company has been changed from <b>{c['former_name'].upper()}</b> to "
              f"<b>{c['name'].upper()}</b> with effect from the date of this certificate and that the company is limited by "
              "shares.")
        doc.p(f"Company was originally incorporated with the name {c['former_name'].upper()}.")
        doc.p("The conversion is pursuant to the special resolution passed by the members at the extraordinary general meeting "
              "held on 10 June 2026 and the approval of the Registrar under Section 18 of the Companies Act, 2013.")
        doc.p("Given under my hand at Manesar this Second day of July Two Thousand Twenty Six.")
    doc.space(10)
    doc.p("Sd/-<br/>Registrar of Companies (specimen; not a real signature)", "right")
    doc.space(10)
    doc.p("Mailing address as per record available in Registrar of Companies office:<br/>" + c["registered_office"], "left")
    doc.p("Note: This is a synthetic specimen created for software testing. It is not issued by, and does not imitate the "
          "emblem, seal or signature of, any government authority.", "small")
    return doc.build()


def allotment_records(d, path):
    c = _co(d)
    doc = Doc(path, "Allotment records", font="Times", size=10)
    for i, a in enumerate(d["allotments"]):
        doc.title("RETURN OF ALLOTMENT - PARTICULARS (EXTRACT)")
        doc.p("[Particulars as filed under Section 39(4) of the Companies Act, 2013 / Section 75 of the Companies Act, 1956]", "center")
        if a["allottees"] == "BONUS":
            allot = {k: v * I.BONUS_RATIO for k, v in d["holdings"]["pre_bonus"].items()}
        else:
            allot = a["allottees"]
        total = sum(allot.values())
        rows = [["Field", "Particulars"],
                ["Corporate identity number", c["former_cin"] if i < 4 else c["cin"]],
                ["Name of the company", c["former_name"] if i < 4 else c["name"]],
                ["Date of allotment", a["date"]],
                ["Nature of allotment", a["nature"]],
                ["Consideration", a["consideration"]],
                ["Number of equity shares allotted", num(total)],
                ["Nominal amount per share (₹)", "10.00"],
                ["Issue price per share (₹)", f"{a['price']:.2f}" if a["price"] else "Nil (bonus)"],
                ["Premium per share (₹)", f"{max(a['price'] - 10, 0):.2f}" if a["price"] else "Nil"],
                ["Total amount received / adjusted (₹)", inr(total * a["price"], 0) if a["price"] else "Nil"],
                ["SRN of e-form", f"SRN-SYN-{2012 + i * 3}-{4471 + i * 137}"]]
        doc.table(rows, [64, 110])
        doc.h3("List of allottees")
        rr = [["Sr.", "Name of allottee", "Number of shares", "Amount (₹)"]]
        for j, (k, v) in enumerate(allot.items(), 1):
            rr.append([str(j), k, num(v), inr(v * a["price"], 0) if a["price"] else "-"])
        rr.append(["", "<b>Total</b>", num(total), inr(total * a["price"], 0) if a["price"] else "-"])
        doc.table(rr, [12, 92, 34, 36], num_cols=(2, 3))
        doc.p("Certified true copy. For " + (c["former_name"] if i < 4 else c["name"]) + "<br/>Sd/- Director", "right")
        doc.br()
    return doc.build()


# ------------------------------------------------------------------ leave and licence ------------
def leave_licence(d, path):
    c = _co(d)
    doc = Doc(path, "Leave and licence agreement - warehouse", font="Times", size=10.5)
    doc.p("STAMP DUTY PAID: ₹1,500 (Gujarat e-stamp, certificate details recorded in the original) - SYNTHETIC", "center")
    doc.space(3)
    doc.title("LEAVE AND LICENCE AGREEMENT")
    doc.p("This Leave and Licence Agreement is made and executed at Ahmedabad on this 28th day of March, 2026,")
    doc.p("<b>BETWEEN</b> Mrs. Kavita Hemant Desai, aged about 49 years, residing at Bungalow No. 12, Shivalik Greens, "
          "Bodakdev, Ahmedabad - 380 054, hereinafter referred to as the 'LICENSOR' (which expression shall, unless repugnant "
          "to the context, include her heirs, executors and assigns) of the ONE PART;")
    doc.p(f"<b>AND</b> {c['former_name']}, a company incorporated under the Companies Act, 1956, having its registered office "
          f"at {c['registered_office']}, through its authorised signatory Mr. Sanjay Prakash Khatri, Chief Financial Officer, "
          "duly authorised by a resolution of its Board of Directors dated 20 March 2026, hereinafter referred to as the "
          "'LICENSEE' of the OTHER PART.")
    doc.p("<b>WHEREAS</b> the Licensor is the absolute owner of Shed No. 7 admeasuring about 1,860 square metres, situated in "
          "Shree Hari Logistics Park, Survey No. 412/2, Village Changodar, Taluka Sanand, District Ahmedabad (the 'Premises'); "
          "AND WHEREAS the Licensee has requested the Licensor to grant leave and licence to use the Premises for storage of "
          "finished goods, and the Licensor has agreed to do so on the terms and conditions set out below.")
    doc.p("<b>NOW THIS AGREEMENT WITNESSETH AS FOLLOWS:</b>")
    terms = [
        "1. <b>Period.</b> The licence shall be for a period of eleven months commencing from 1 April 2026 and ending on "
        "28 February 2027, which may be renewed by mutual consent in writing on such terms as may be agreed.",
        "2. <b>Licence fee.</b> The Licensee shall pay to the Licensor a monthly licence fee of ₹1,25,000 (Rupees One Lakh "
        "Twenty-Five Thousand only), exclusive of goods and services tax, on or before the 7th day of each month, by bank "
        "transfer, after deduction of tax at source as applicable.",
        "3. <b>Security deposit.</b> The Licensee has paid an interest-free refundable security deposit of ₹5,00,000 "
        "(Rupees Five Lakh only), which shall be refunded on expiry or earlier termination of this agreement against "
        "handing over of vacant and peaceful possession of the Premises.",
        "4. <b>Escalation.</b> On renewal, the licence fee may be increased by up to 5% over the last licence fee paid.",
        "5. <b>Use.</b> The Licensee shall use the Premises only for the purpose of warehousing of packaging materials and "
        "finished goods and shall not store hazardous or inflammable materials other than in quantities permitted by law.",
        "6. <b>Maintenance and outgoings.</b> Property tax and structural repairs shall be borne by the Licensor. Electricity, "
        "water charges and day-to-day maintenance shall be borne by the Licensee.",
        "7. <b>No tenancy.</b> Nothing contained herein shall be construed as creating any tenancy, sub-tenancy or lease in "
        "favour of the Licensee, and the Licensee shall have no right, title or interest in the Premises.",
        "8. <b>Termination.</b> Either party may terminate this agreement by giving three months' notice in writing. The "
        "lock-in period shall be six months from the commencement date.",
        "9. <b>Related party.</b> The parties acknowledge that the Licensor is a director and shareholder of the Licensee and "
        "that this transaction has been approved by the Board of Directors of the Licensee as being in the ordinary course of "
        "business and on an arm's length basis.",
        "10. <b>Registration.</b> This agreement shall be registered with the Sub-Registrar, Sanand, and the stamp duty and "
        "registration charges shall be borne equally by the parties.",
        "11. <b>Jurisdiction.</b> The courts at Ahmedabad shall have exclusive jurisdiction in respect of any dispute arising "
        "out of this agreement.",
    ]
    doc.ps(terms)
    doc.p("<b>SCHEDULE OF THE PREMISES:</b> Shed No. 7 with appurtenant open area, total built-up area about 1,860 sq m, "
          "bounded on the North by Shed No. 6, on the South by internal road, on the East by Shed No. 8 and on the West by "
          "the compound wall.")
    doc.p("IN WITNESS WHEREOF the parties have signed this agreement on the day and year first above written.")
    doc.table([["LICENSOR", "LICENSEE"],
               ["Sd/-<br/>Kavita Hemant Desai", f"Sd/-<br/>For {c['former_name']}<br/>Sanjay Prakash Khatri, Authorised Signatory"],
               ["Witness 1: Sd/- Jayesh R. Parmar, Ahmedabad", "Witness 2: Sd/- Nilesh K. Bhatt, Ahmedabad"]], [87, 87])
    doc.p("Registered at the office of the Sub-Registrar, Sanand as document No. SND/3184/2026 on 2 April 2026 (synthetic).", "small")
    return doc.build()


# ------------------------------------------------------------------ bank sanction letters -------
def bank_letterhead():
    return ("KALINDI BANK LIMITED", "Navrangpura Branch: Ground Floor, Sahajanand Arcade, Navrangpura, Ahmedabad - 380 009",
            "MSME and Mid-Corporate Credit Hub  |  IFSC: KLDB0001428 (synthetic)  |  Fictitious bank for testing")


def sanction_letter(d, path):
    c = _co(d)
    L1, CC = d["loans"]["TL1"], d["loans"]["CC"]
    doc = Doc(path, "Sanction letter", letterhead=bank_letterhead())
    doc.p("Ref: KBL/NVP/MSME/2025-26/0718", "left")
    doc.p("Date: 14 August 2025", "right")
    doc.p(f"To,<br/>The Board of Directors,<br/>{c['former_name']}<br/>{c['registered_office']}", "left")
    doc.p("<b>Sub: Renewal and enhancement of working capital limits and review of term loans - Sanction letter</b>")
    doc.p("Dear Sir / Madam,")
    doc.p("With reference to your application dated 12 June 2025 and subsequent discussions, we are pleased to inform you that "
          "the Bank has sanctioned / renewed the following credit facilities, subject to the terms and conditions mentioned "
          "below and in the annexures:")
    rows = [["Facility", "Existing limit (₹ lakhs)", "Sanctioned limit (₹ lakhs)", "Rate of interest", "Tenor / repayment"],
            ["Cash credit (hypothecation of stocks and book debts)", "1,800.00", inr(CC["sanctioned"]), CC["rate"].replace(" (9.60% p.a. at 30 Sep 2026)", " (presently 9.60% p.a.)"), "12 months, renewable"],
            ["Term loan TL-I (plant and machinery)", inr(240.00) + " (o/s)", "Continued", "Repo + 3.75%", "54 EMIs ending March 2027"],
            ["Term loan TL-II (solventless laminator)", inr(684.00) + " (o/s)", "Continued", "Repo + 3.75%", "60 monthly principal instalments of ₹12.00 lakhs from January 2025"],
            ["Inland / import letter of credit (sub-limit of CC)", "150.00", "200.00", "Commission as per schedule", "Usance up to 120 days"],
            ["Bank guarantee", "50.00", "75.00", "Commission 1.25% p.a.", "Up to 36 months"]]
    doc.table(rows, [52, 26, 26, 34, 36], num_cols=(1, 2))
    doc.h2("Key terms and conditions")
    tc = [
        "1. <b>Margin:</b> 25% on stocks and 40% on book debts not older than 120 days. Drawing power to be computed on the "
        "basis of monthly stock and book-debt statements submitted by the 10th of the following month.",
        "2. <b>Primary security:</b> first hypothecation charge on the entire current assets of the Company, present and future; "
        "exclusive hypothecation of machinery financed under TL-I and TL-II.",
        "3. <b>Collateral security:</b> equitable mortgage by deposit of title deeds (extension) of leasehold land and factory "
        "building at Plot No. 214-216, GIDC Sanand-II, Ahmedabad, valued at ₹2,840.00 lakhs as per valuation report dated "
        "2 July 2025.",
        "4. <b>Guarantees:</b> unconditional and irrevocable personal guarantees of Mr. Hemant Ramniklal Desai and Mrs. Kavita "
        "Hemant Desai, with net worth statements as on 31 March 2025.",
        "5. <b>Financial covenants:</b> TOL/TNW not to exceed 2.00x; current ratio not below 1.25x; DSCR not below 1.40x; "
        "to be tested on the audited financial statements annually.",
        "6. <b>Negative covenants:</b> the Company shall not, without the prior written consent of the Bank: (a) effect any change "
        "in its capital structure or shareholding pattern, including by way of public issue; (b) declare dividend if any "
        "instalment is overdue; (c) undertake any new project or expansion except as disclosed to the Bank; (d) repay "
        "unsecured loans from promoters while bank dues are outstanding; (e) change its management or constitution.",
        "7. <b>Prepayment:</b> prepayment of term loans out of equity raised by the Company is permitted without prepayment "
        "charges, with 30 days' notice.",
        "8. <b>Insurance:</b> all assets charged to the Bank to be insured against fire and allied perils with the Bank's clause.",
        "9. <b>Processing charges:</b> 0.30% of the enhanced limit plus GST.",
        "10. <b>Validity:</b> this sanction is valid for acceptance within 30 days of the date of this letter.",
    ]
    doc.ps(tc)
    doc.p("Please return the duplicate copy of this letter duly signed by the authorised signatories and guarantors in token "
          "of acceptance of the terms and conditions.")
    doc.signature(["For Kalindi Bank Limited", "", "Sd/-", "Chief Manager - MSME Credit"], left=["Accepted:", "Sd/- Hemant Ramniklal Desai, Managing Director",
                                                                                                "Sd/- Kavita Hemant Desai, Guarantor"])
    doc.br()
    doc.title("ANNEXURE - TERM LOAN TL-II (ORIGINAL SANCTION DATED 26 JUNE 2024)")
    rows = [["Particulars", "Details"],
            ["Purpose", "Purchase of solventless laminator 1,300 mm, 400 m/min, and allied equipment"],
            ["Project cost", "₹1,020.00 lakhs (machine ₹905.00 lakhs, installation and electricals ₹115.00 lakhs)"],
            ["Means of finance", "Term loan ₹750.00 lakhs; promoters' contribution / internal accruals ₹270.00 lakhs"],
            ["Sanctioned amount", inr(L1["sanctioned"])],
            ["Amount disbursed", "₹720.00 lakhs (balance cancelled on completion of the project below cost)"],
            ["Interest", L1["rate"]],
            ["Repayment", L1["tenure"]],
            ["Security", L1["security"]],
            ["Outstanding as on 31 March 2025", "₹684.00 lakhs"]]
    doc.table(rows, [48, 126])
    return doc.build()


def gst_certificate(d, path):
    c = _co(d)
    doc = Doc(path, "GST registration certificate", page_numbers=True)
    doc.title("Government of India<br/>Form GST REG-06 (format illustration)<br/>Registration Certificate")
    rows = [["Registration Number", c["gstin"]],
            ["1. Legal name", c["name"].upper()],
            ["2. Trade name, if any", "ASHTAVIRA FLEXIPAK"],
            ["3. Constitution of business", "Public Limited Company"],
            ["4. Address of principal place of business", c["registered_office"]],
            ["5. Date of liability", "01/07/2017"],
            ["6. Date of validity", "From 01/07/2017 To Not Applicable"],
            ["7. Type of registration", "Regular"],
            ["8. Particulars of approving authority", "Centre: Ahmedabad Commissionerate, Range-III Sanand"],
            ["9. Date of issue of certificate (amendment of legal name)", "18/07/2026"]]
    doc.table(rows, [70, 104])
    doc.h2("Annexure A - Additional places of business")
    doc.table([["Sr.", "Address"],
               ["1", c["warehouse"]],
               ["2", c["corporate_office"]]], [12, 162])
    doc.h2("Annexure B - Details of managing / authorised partners / directors")
    doc.table([["Name", "Designation / status", "Resident of State"],
               ["Hemant Ramniklal Desai", "Managing Director", "Gujarat"],
               ["Kavita Hemant Desai", "Whole-time Director", "Gujarat"],
               ["Parth Hemant Desai", "Whole-time Director", "Gujarat"]], [70, 60, 44])
    doc.p("This is a system-generated format illustration with synthetic data; it is not issued by the GST Network.", "small")
    return doc.build()


def licence_page(d, path, kind):
    """One-page licence used as an image source (factory licence, CC&A, fire NOC)."""
    c = _co(d)
    lic = {x[0]: x for x in d["licences"]}
    if kind == "factory":
        t = lic["Factory licence"]
        title = "LICENCE TO WORK A FACTORY<br/>(Under Section 6 of the Factories Act, 1948 and the Gujarat Factories Rules, 1963)"
        body = [("Licence No.", t[2]), ("Name of factory", c["former_name"]), ("Address", c["factory"]),
                ("Nature of manufacturing process", "Printing, lamination and conversion of flexible packaging materials"),
                ("Maximum number of workers", "300"), ("Maximum installed power", "1,500 kW"),
                ("Date of first issue", t[3]), ("Valid up to", t[4]), ("Renewal fee paid", "₹48,600 (challan dated 12 December 2025)")]
        issuer_line = "Deputy Director, Industrial Safety and Health, Ahmedabad (specimen)"
    elif kind == "cca":
        t = lic["Consolidated Consent and Authorisation (CC&A) under Water Act, Air Act and Hazardous Waste Rules"]
        title = "CONSOLIDATED CONSENT AND AUTHORISATION (CC&A)<br/>Gujarat Pollution Control Board - format illustration"
        body = [("CC&A No.", t[2]), ("Industry", c["former_name"]), ("Location", c["factory"]),
                ("Category", "Orange - Large"), ("Products", "Printed laminated films and pouches: 9,600 MT per annum"),
                ("Trade effluent", "Nil (zero liquid discharge); domestic effluent 6 KL/day to soak pit"),
                ("Air emission sources", "Thermic fluid heater (PNG fired), DG sets 2 x 625 kVA, laminator and printing hoods with VOC control"),
                ("Hazardous waste", "Used oil (5.1) 0.3 KL/year; discarded containers (33.1) 2,400 nos/year; ink sludge (21.1) 6 MT/year"),
                ("Date of issue", t[3]), ("Valid up to", t[4])]
        issuer_line = "Unit Head, Regional Office, Ahmedabad (Rural) (specimen)"
    else:
        t = lic["Fire safety certificate (NOC)"]
        title = "FIRE SAFETY CERTIFICATE<br/>(Gujarat Fire Prevention and Life Safety Measures Act, 2013) - format illustration"
        body = [("Certificate No.", t[2]), ("Occupier", c["former_name"]), ("Premises", c["factory"]),
                ("Occupancy", "Industrial (moderate hazard)"), ("Built-up area", "9,420 sq m"),
                ("Fire-fighting installations", "Hydrant system, sprinklers in finished-goods store, 62 extinguishers, fire alarm"),
                ("Date of issue", t[3]), ("Valid up to", t[4])]
        issuer_line = "Chief Fire Officer (specimen)"
    doc = Doc(path, title.split("<br/>")[0], page_numbers=False)
    doc.title(title)
    doc.space(3)
    doc.table([["Particulars", "Details"]] + [[a, b] for a, b in body], [56, 118])
    doc.p("Conditions: The licence / consent is subject to the conditions printed overleaf and to compliance with the "
          "applicable rules. Any change in the process, capacity or premises shall be intimated in advance.")
    doc.space(10)
    doc.p("Sd/-<br/>" + issuer_line, "right")
    doc.p("Synthetic specimen for software testing; not issued by any authority.", "small")
    return doc.build()


# ------------------------------------------------------------------ quotations -----------------
def quotation_pages(d, path):
    """Supplier quotations for the plant and machinery object (to be scanned)."""
    doc = Doc(path, "Machinery quotations", watermark=True)
    groups = {}
    for m in d["machinery"]:
        groups.setdefault((m["supplier"], m["quote_no"]), []).append(m)
    c = _co(d)
    for (sup, qno), items in groups.items():
        m0 = items[0]
        doc.title(sup.upper())
        doc.p(f"{m0['place']}  |  sales@{sup.split()[0].lower()}-synthetic.example", "center")
        doc.space(2)
        doc.p(f"Quotation No.: {qno}" + "&nbsp;" * 30 + f"Date: {m0['quote_date']}", "left")
        doc.p(f"To: {c['name']}, {c['factory']}<br/>Kind attn.: Mr. Rakesh Joshi, Plant Head", "left")
        doc.p("Dear Sir, with reference to your enquiry and the technical discussions held, we are pleased to quote as under:")
        rows = [["Sr.", "Description", "Qty", "Unit price", "Amount"]]
        for i, m in enumerate(items, 1):
            if m["currency"] == "EUR":
                rows.append([str(i), m["item"], str(m["qty"]), f"EUR {num(m['unit_price_fx'])}", f"EUR {num(m['unit_price_fx'] * m['qty'])}"])
            else:
                rows.append([str(i), m["item"], str(m["qty"]), "₹" + inr(m["unit_price"] * 1e5, 0), "₹" + inr(m["amount"] * 1e5, 0)])
        doc.table(rows, [10, 92, 12, 30, 30], num_cols=(2, 3, 4))
        terms = [f"Prices: {'FCA Hamburg, excluding customs duty, freight and insurance' if m0['currency'] == 'EUR' else 'ex-works, excluding GST at 18%, freight, insurance and installation'}.",
                 "Payment: 30% advance with purchase order, 60% against proforma invoice before dispatch, 10% after "
                 "installation and commissioning." if m0["currency"] == "INR" else "Payment: 20% advance by TT, 80% by irrevocable LC at sight.",
                 f"Delivery: {m0['delivery']}.", f"Validity: {m0['valid_till']}.",
                 "Warranty: 12 months from commissioning or 18 months from dispatch, whichever is earlier.",
                 "Installation and commissioning by our engineers; to-and-fro travel and boarding at buyer's cost."]
        doc.h3("Terms and conditions")
        for t in terms:
            doc.p("&bull; " + t, "left")
        doc.signature([f"For {sup}", "", "Sd/-", "Authorised signatory"])
        doc.br()
    return doc.build()


def solar_quotation(d, path):
    s = d["solar"]
    c = _co(d)
    doc = Doc(path, "Solar EPC quotation", letterhead=(s["supplier"].upper(), s["place"] + "  |  MNRE-empanelled EPC (synthetic)",
                                                       "epc@suryamitra-synthetic.example"))
    doc.p(f"Ref: {s['quote_no']}", "left")
    doc.p(f"Date: {s['quote_date']}", "right")
    doc.p(f"To: {c['name']}<br/>{c['factory']}", "left")
    doc.p(f"<b>Sub: Techno-commercial offer for {s['capacity_mwp']:.2f} MWp grid-connected rooftop solar PV plant (CAPEX model)</b>")
    doc.p("We thank you for the opportunity to quote. Based on the site survey of the factory roofs (metal sheet roof, "
          "approximately 9,000 sq m shadow-free area) conducted on 22 September 2026, we propose the following:")
    rows = [["Sr.", "Scope", "Amount (₹ lakhs)"]]
    for i, (it, amt) in enumerate(s["items"], 1):
        rows.append([str(i), it, inr(amt)])
    rows.append(["", "<b>Total (excluding GST)</b>", inr(s["amount"])])
    doc.table(rows, [10, 130, 34], num_cols=(2,), total_rows=(len(rows) - 1,))
    doc.h2("Expected generation and savings")
    doc.table([["Parameter", "Value"],
               ["Plant capacity (DC)", f"{s['capacity_mwp']:.2f} MWp"],
               ["Expected first-year generation (P50)", f"{num(s['annual_generation_mwh'])} MWh"],
               ["Annual degradation", "0.5% (year 2 onwards)"],
               ["Current grid tariff (HT, energy + demand, blended)", "₹8.40 per kWh"],
               ["Estimated first-year saving", "₹147.17 lakhs"],
               ["Simple payback", "About 3.5 years"]], [90, 84])
    doc.p("The generation estimate is based on PVsyst simulation with Meteonorm data for Sanand; actual generation depends on "
          "irradiation, grid availability and maintenance. Net-metering is subject to approval of the distribution company.")
    doc.h2("Commercial terms")
    for t in ["Payment: 20% advance, 60% against material delivery, 20% on commissioning.",
              "Completion: 16 weeks from advance and approvals.", f"Validity: {s['valid_till']}.",
              "Warranty: modules 12 years product / 30 years linear performance; inverters 5 years; workmanship 5 years."]:
        doc.p("&bull; " + t, "left")
    doc.signature([f"For {s['supplier']}", "", "Sd/-", "Head - Commercial & Industrial Projects"])
    return doc.build()
