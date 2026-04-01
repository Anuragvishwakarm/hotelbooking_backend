import io
from datetime import datetime, timezone
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

PRIMARY  = colors.HexColor("#1A3C5E")
ACCENT   = colors.HexColor("#2E86AB")
LIGHT_BG = colors.HexColor("#F4F7FA")
ROW_ALT  = colors.HexColor("#EAF0F6")
TEXT_G   = colors.HexColor("#636366")
SUCCESS  = colors.HexColor("#1A7F37")
WARNING  = colors.HexColor("#B45309")


def _fmt(val) -> str:
    try:
        return f"Rs. {Decimal(str(val)):,.2f}"
    except Exception:
        return str(val)


def generate_invoice_pdf(booking, hotel, guest_user, folio, payments: list) -> bytes:
    """Generate a GST-compliant A4 PDF invoice. Returns raw PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
        title=f"Invoice {folio.folio_number}",
    )
    styles = getSampleStyleSheet()
    N = styles["Normal"]
    right_style = ParagraphStyle("R", parent=N, alignment=TA_RIGHT)
    center_style = ParagraphStyle("C", parent=N, alignment=TA_CENTER)
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    hdata = [[
        Paragraph(
            f"<font size='16' color='#1A3C5E'><b>{hotel.name}</b></font><br/>"
            f"<font size='8' color='#636366'>{hotel.address}, {hotel.city} - {hotel.pincode}, {hotel.state}<br/>"
            f"Ph: {hotel.phone}" + (f" | {hotel.email}" if hotel.email else "") + "</font>",
            N,
        ),
        Paragraph(
            "<font size='18' color='#1A3C5E'><b>TAX INVOICE</b></font><br/><br/>"
            f"<font size='8' color='#636366'>Invoice No: </font>"
            f"<font size='8'><b>{folio.folio_number}</b></font><br/>"
            f"<font size='8' color='#636366'>Booking Ref: </font>"
            f"<font size='8'><b>{booking.booking_ref}</b></font><br/>"
            f"<font size='8' color='#636366'>Date: </font>"
            f"<font size='8'>{datetime.now(timezone.utc).strftime('%d %b %Y')}</font>",
            right_style,
        ),
    ]]
    ht = Table(hdata, colWidths=[95*mm, 85*mm])
    ht.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), LIGHT_BG),
        ("VALIGN",     (0,0),(-1,-1), "TOP"),
        ("TOPPADDING", (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LEFTPADDING", (0,0),(0,-1), 10),
        ("RIGHTPADDING",(-1,0),(-1,-1), 10),
    ]))
    story.append(ht)
    story.append(Spacer(1, 4*mm))

    # ── GST strip ─────────────────────────────────────────────────────────────
    if hotel.gst_number:
        gd = [[
            Paragraph(f"<font size='8' color='#636366'>GSTIN: </font><font size='8'><b>{hotel.gst_number}</b></font>", N),
            Paragraph(f"<font size='8' color='#636366'>PAN: </font><font size='8'>{hotel.pan_number or 'N/A'}</font>", N),
            Paragraph("<font size='8' color='#636366'>SAC Code: </font><font size='8'>996311</font>", N),
        ]]
        gt = Table(gd, colWidths=[60*mm, 60*mm, 60*mm])
        gt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), colors.HexColor("#E8F4FD")),
            ("TOPPADDING",(0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING",(0,0),(-1,-1), 8),
        ]))
        story.append(gt)
        story.append(Spacer(1, 3*mm))

    # ── Guest & Stay info ─────────────────────────────────────────────────────
    ci  = booking.check_in_date.strftime("%d %b %Y")
    co  = booking.check_out_date.strftime("%d %b %Y")
    aci = booking.actual_check_in.strftime("%d %b %Y %H:%M") if booking.actual_check_in else "—"
    aco = booking.actual_check_out.strftime("%d %b %Y %H:%M") if booking.actual_check_out else "—"
    rt_name = booking.room_type.name if booking.room_type else "—"
    rm_num  = booking.room.room_number if booking.room else "—"

    idata = [
        [
            Paragraph("<b><font size='8' color='white'>BILL TO</font></b>", N),
            Paragraph("<b><font size='8' color='white'>STAY DETAILS</font></b>", N),
        ],
        [
            Paragraph(
                f"<font size='9'><b>{guest_user.full_name}</b></font><br/>"
                f"<font size='8' color='#636366'>Phone: {guest_user.phone}</font>"
                + (f"<br/><font size='8' color='#636366'>Email: {guest_user.email}</font>" if guest_user.email else ""),
                N,
            ),
            Paragraph(
                f"<font size='8'>Room Type: <b>{rt_name}</b> | Room No: <b>{rm_num}</b><br/>"
                f"Check-in:  <b>{ci}</b>  (actual: {aci})<br/>"
                f"Check-out: <b>{co}</b>  (actual: {aco})<br/>"
                f"Nights: <b>{booking.num_nights}</b>  |  "
                f"Guests: <b>{booking.adults}A"
                + (f"+{booking.children}C" if booking.children else "") +
                f"</b>  |  Meal: <b>{booking.meal_plan.value.upper()}</b></font>",
                N,
            ),
        ],
    ]
    it = Table(idata, colWidths=[90*mm, 90*mm])
    it.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), PRIMARY),
        ("BACKGROUND",(0,1),(-1,-1), colors.white),
        ("BOX",(0,0),(-1,-1), 0.5, colors.HexColor("#D1D1D6")),
        ("LINEBEFORE",(1,0),(1,-1), 0.5, colors.HexColor("#D1D1D6")),
        ("TOPPADDING",(0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING",(0,0),(-1,-1), 8),
        ("VALIGN",(0,0),(-1,-1), "TOP"),
    ]))
    story.append(it)
    story.append(Spacer(1, 5*mm))

    # ── Folio items ───────────────────────────────────────────────────────────
    story.append(Paragraph("<b><font size='10' color='#1A3C5E'>Itemised Bill</font></b>", N))
    story.append(Spacer(1, 2*mm))

    rows = [["#", "Description", "Category", "Date", "Qty", "Rate", "Amount"]]
    for i, item in enumerate(folio.items, 1):
        rows.append([
            str(i),
            item.description,
            item.category.value.replace("_"," ").title(),
            item.date.strftime("%d %b") if item.date else "—",
            str(item.quantity),
            _fmt(item.unit_price),
            _fmt(item.amount),
        ])

    col_w = [8*mm, 55*mm, 28*mm, 18*mm, 10*mm, 26*mm, 25*mm]
    ftable = Table(rows, colWidths=col_w)
    fstyle = TableStyle([
        ("BACKGROUND",(0,0),(-1,0), PRIMARY),
        ("TEXTCOLOR",(0,0),(-1,0), colors.white),
        ("FONTNAME",(0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1), 8),
        ("ALIGN",(4,0),(-1,-1), "RIGHT"),
        ("ALIGN",(0,0),(0,-1), "CENTER"),
        ("GRID",(0,0),(-1,-1), 0.3, colors.HexColor("#D1D1D6")),
        ("TOPPADDING",(0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING",(0,0),(-1,-1), 5),
    ])
    for i in range(1, len(rows)):
        fstyle.add("BACKGROUND", (0,i),(-1,i), ROW_ALT if i%2==0 else colors.white)
    ftable.setStyle(fstyle)
    story.append(ftable)
    story.append(Spacer(1, 4*mm))

    # ── Totals ────────────────────────────────────────────────────────────────
    subtotal = Decimal(str(folio.subtotal))
    gst_amt  = Decimal(str(folio.gst_amount))
    total    = Decimal(str(folio.total))
    paid     = Decimal(str(folio.paid))
    balance  = Decimal(str(folio.balance))
    cgst = sgst = gst_amt / 2

    trows = [
        ["", "Subtotal",    _fmt(subtotal)],
        ["", "CGST (9%)",   _fmt(cgst)],
        ["", "SGST (9%)",   _fmt(sgst)],
        ["", "Grand Total", _fmt(total)],
        ["", "Paid",        _fmt(paid)],
        ["", "Balance Due", _fmt(balance)],
    ]
    ttable = Table(trows, colWidths=[100*mm, 50*mm, 30*mm])
    tstyle = TableStyle([
        ("ALIGN",(1,0),(-1,-1), "RIGHT"),
        ("FONTSIZE",(0,0),(-1,-1), 9),
        ("TOPPADDING",(0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("LINEABOVE",(1,3),(-1,3), 1.0, PRIMARY),
        ("FONTNAME",(1,3),(-1,3), "Helvetica-Bold"),
        ("FONTSIZE",(1,3),(-1,3), 10),
        ("TEXTCOLOR",(1,3),(-1,3), PRIMARY),
        ("LINEABOVE",(1,4),(-1,4), 0.4, colors.HexColor("#D1D1D6")),
        ("FONTNAME",(1,5),(-1,5), "Helvetica-Bold"),
        ("BACKGROUND",(1,5),(-1,5),
         colors.HexColor("#FEF3C7") if float(balance)>0 else colors.HexColor("#D1FAE5")),
        ("TEXTCOLOR",(1,5),(-1,5),
         WARNING if float(balance)>0 else SUCCESS),
    ])
    ttable.setStyle(tstyle)
    story.append(ttable)
    story.append(Spacer(1, 5*mm))

    # ── Payment history ───────────────────────────────────────────────────────
    if payments:
        story.append(Paragraph("<b><font size='9' color='#1A3C5E'>Payment History</font></b>", N))
        story.append(Spacer(1, 2*mm))
        prows = [["#","Date & Time","Method","Ref / TxnID","Amount","Status"]]
        for i, p in enumerate(payments, 1):
            pdate = p.paid_at.strftime("%d %b %Y %H:%M") if p.paid_at else "—"
            ref   = p.razorpay_payment_id or p.upi_transaction_id or p.bank_reference or "—"
            prows.append([str(i), pdate, p.method.value.upper(), ref[:22], _fmt(p.amount), p.status.value.upper()])
        ptable = Table(prows, colWidths=[8*mm, 36*mm, 22*mm, 44*mm, 28*mm, 22*mm])
        ptable.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0), ACCENT),
            ("TEXTCOLOR",(0,0),(-1,0), colors.white),
            ("FONTSIZE",(0,0),(-1,-1), 8),
            ("ALIGN",(4,0),(5,-1), "RIGHT"),
            ("GRID",(0,0),(-1,-1), 0.3, colors.HexColor("#D1D1D6")),
            ("TOPPADDING",(0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING",(0,0),(-1,-1), 5),
        ]))
        story.append(ptable)
        story.append(Spacer(1, 5*mm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#D1D1D6")))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        f"<font size='7' color='#8E8E93'>Computer-generated invoice — no signature required. "
        f"SAC Code 996311 | GST applied as per Indian hotel tariff slabs. "
        f"Generated {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}.</font>",
        center_style,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()
