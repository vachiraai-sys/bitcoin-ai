import os
import csv
import json
from collections import defaultdict, deque
from openpyxl import Workbook


def read_csv_with_header_row3(file_path, source_name=None):
    """อ่าน CSV โดยมี header อยู่ที่แถว 3"""
    with open(file_path, encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
        if len(rows) < 3:
            return []

        headers = [h.strip() for h in rows[2]]
        data_rows = rows[3:]

        transactions = []
        for row in data_rows:
            if not any(row):
                continue
            entry = dict(zip(headers, row))
            if source_name:
                entry["source"] = source_name
            transactions.append(entry)
        return transactions


import zipfile
import tempfile


def read_csv_from_string(content, source_name=None):
    """อ่าน CSV จาก string content (ใช้กับ zip)"""
    lines = content.splitlines()
    if len(lines) < 3:
        return []
    
    # ใช้ csv reader กับ lines
    reader = csv.reader(lines)
    rows = list(reader)
    
    headers = [h.strip() for h in rows[2]]
    data_rows = rows[3:]

    transactions = []
    for row in data_rows:
        if not any(row):
            continue
        entry = dict(zip(headers, row))
        if source_name:
            entry["source"] = source_name
        transactions.append(entry)
    return transactions


def collect_all_csv(folder_path, password=None):
    """อ่าน CSV และ ZIP ทุกไฟล์ทุกโฟลเดอร์ย่อย (รองรับรหัสผ่าน ZIP)"""
    all_transactions = []
    zip_pwd = password.encode('utf-8') if password else None
    
    for root, _, files in os.walk(folder_path):
        # สร้างชื่อโฟลเดอร์สัมพัทธ์เพื่อเป็น source
        rel_root = os.path.relpath(root, folder_path)
        
        for file in files:
            full_path = os.path.join(root, file)
            display_name = os.path.join(rel_root, file) if rel_root != "." else file
            
            if file.lower().endswith(".csv"):
                txns = read_csv_with_header_row3(full_path, source_name=display_name)
                all_transactions.extend(txns)
            elif file.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(full_path, 'r') as z:
                        for z_info in z.infolist():
                            if z_info.filename.lower().endswith(".csv"):
                                try:
                                    content = z.read(z_info.filename, pwd=zip_pwd).decode('utf-8-sig')
                                    # รวมชื่อไฟล์ zip เข้ากับชื่อไฟล์ข้างใน
                                    inner_source = f"{display_name} > {z_info.filename}"
                                    txns = read_csv_from_string(content, source_name=inner_source)
                                    all_transactions.extend(txns)
                                except RuntimeError as e:
                                    if "encrypted" in str(e):
                                        print(f"⚠️ ไฟล์ {file} ติดรหัสผ่าน (Skipped)")
                                    else:
                                        print(f"⚠️ Error reading {z_info.filename}: {e}")

                except Exception as e:
                    print(f"⚠️ Error opening zip {file}: {e}")
    return all_transactions





def normalize_transaction(txn):
    """ปรับชื่อคีย์และแปลงประเภทข้อมูล"""
    return {
        "txn_id": txn.get("txn_id") or txn.get("Transaction ID", ""),
        "currency": txn.get("currency") or txn.get("Currency", ""),
        "created_date": txn.get("created_date") or txn.get("Date", ""),
        "side": txn.get("side") or txn.get("Side", ""),
        "amount": float(txn.get("amount") or txn.get("Amount", 0) or 0),
        "thb_exec_price": float(txn.get("thb_exec_price") or txn.get("Price (THB)", 0) or 0),
        "thb_exec_val": float(txn.get("thb_exec_val") or txn.get("THB Value", 0) or 0),
        "fee": float(txn.get("fee") or txn.get("Fee", 0) or 0),
        "thb_net": float(txn.get("thb_net") or txn.get("Net (THB)", 0) or 0),
        "source": txn.get("source") or "Upload"
    }



def fifo_profit_loss(transactions):
    """คำนวณกำไร/ขาดทุนแบบ FIFO สำหรับแต่ละเหรียญ"""
    by_currency = defaultdict(list)
    for t in transactions:
        if t["currency"]:
            by_currency[t["currency"]].append(t)

    results = {}
    for coin, txns in by_currency.items():
        # เรียงตามเวลา
        txns.sort(key=lambda x: x["created_date"])
        buy_queue = deque()
        total_profit = 0.0

        for t in txns:
            side = t["side"].lower()
            amount = t["amount"]
            price = t["thb_exec_price"]
            value = t["thb_exec_val"]

            if side == "buy":
                buy_queue.append({"amount": amount, "price": price})
            elif side == "sell":
                sell_amount = amount
                sell_price = price

                # ใช้ FIFO
                while sell_amount > 0 and buy_queue:
                    buy_lot = buy_queue[0]
                    qty_used = min(sell_amount, buy_lot["amount"])
                    cost_basis = qty_used * buy_lot["price"]
                    proceeds = qty_used * sell_price
                    profit = proceeds - cost_basis
                    total_profit += profit

                    buy_lot["amount"] -= qty_used
                    if buy_lot["amount"] <= 0:
                        buy_queue.popleft()
                    sell_amount -= qty_used

        results[coin] = round(total_profit, 2)
    return results


def export_to_excel(profit_data, output_file="profit_summary.xlsx"):
    """บันทึกผลกำไรลง Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Profit Summary"

    ws.append(["Currency", "Net Profit (THB)"])
    for coin, profit in profit_data.items():
        ws.append([coin, profit])

    ws.append([])
    ws.append(["Total", sum(profit_data.values())])

    wb.save(output_file)
    print(f"✅ บันทึกไฟล์เรียบร้อย: {output_file}")


def main(folder_path):
    all_txns = collect_all_csv(folder_path)
    normalized = [normalize_transaction(t) for t in all_txns]
    profit_data = fifo_profit_loss(normalized)
    export_to_excel(profit_data, f"{folder_path}/profit_summary.xlsx")

    # บันทึกเป็น JSON ไว้ด้วย
    with open(f"{folder_path}/transactions.json", "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print("✅ แปลง CSV → JSON + คำนวณกำไร/ขาดทุนแบบ FIFO สำเร็จ")


if __name__ == "__main__":
    folder = input("กรุณาใส่ path ของโฟลเดอร์ที่เก็บ CSV: ").strip()
    if os.path.isdir(folder):
        main(folder)
    else:
        print(f"❌ โฟลเดอร์ไม่ถูกต้อง: {folder}")

