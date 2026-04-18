"""
Script 3: Tạo Sale Orders vào Odoo 17 qua XML-RPC.
Dữ liệu bán hàng 01/01/2026 – 10/04/2026 cho 3 kịch bản AI.
  KB1: Spike bất thường RAM DDR5 16GB Kingston cuối tháng 3
  KB2: Margin âm do giá nhập tăng (xử lý ở PO)
  KB3: Churn VIP – Thế Giới PC ngừng mua sau 25/03
"""

import xmlrpc.client
import random
import datetime
import math

random.seed(42)

URL = "http://educare-connect.me"
DB = "erpsight"
USER = "admin"
PASS = "admin"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(DB, USER, PASS, {})
if not uid:
    raise SystemExit("Xác thực thất bại.")
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)


def execute(model, method, *args, **kwargs):
    call_args = list(args)
    if method in ("search", "search_read", "search_count") and call_args:
        d = call_args[0]
        if isinstance(d, list) and len(d) == 1 and isinstance(d[0], list):
            call_args[0] = d[0]
    return models.execute_kw(DB, uid, PASS, model, method, call_args, kwargs)


# ── Lookup helpers ──────────────────────────────────────────────────────────

def find_product(ref):
    recs = execute("product.product", "search_read",
                   [[("default_code", "=", ref)]], fields=["id"], limit=1)
    return recs[0]["id"] if recs else None


def find_partner(name):
    recs = execute("res.partner", "search_read",
                   [[("name", "ilike", name)]], fields=["id"], limit=1)
    return recs[0]["id"] if recs else None


def find_user(login):
    recs = execute("res.users", "search_read",
                   [[("login", "=", login)]], fields=["id"], limit=1)
    return recs[0]["id"] if recs else uid  # fallback admin


# ── Hằng số ─────────────────────────────────────────────────────────────────

START_DATE = datetime.date(2026, 1, 1)
END_DATE = datetime.date(2026, 4, 10)

DOW_MULT = {0: 1.2, 1: 1.2, 2: 1.0, 3: 1.0, 4: 0.8, 5: 0.3, 6: 0.1}

TG_PC_DATES = [
    datetime.date(2026, 1, 10), datetime.date(2026, 1, 20), datetime.date(2026, 1, 30),
    datetime.date(2026, 2, 9),  datetime.date(2026, 2, 19),
    datetime.date(2026, 3, 1),  datetime.date(2026, 3, 11), datetime.date(2026, 3, 21),
    datetime.date(2026, 3, 25),
]

# List prices (để tính giá bán sau chiết khấu)
PRODUCT_DEFS = {
    "RAM-DDR5-16-KS":  2200000,
    "RAM-DDR5-32-KS":  4100000,
    "RAM-DDR5-16-SS":  2350000,
    "RAM-DDR5-32-CO":  4300000,
    "SSD-1TB-SS-870":  1750000,
    "SSD-2TB-SS-870":  3200000,
    "SSD-512-WD-BL":   890000,
    "SSD-1TB-WD-BL":   1580000,
    "HDD-2TB-SG-BC":   1100000,
    "HDD-4TB-SG-BC":   1950000,
    "HDD-2TB-WD-BL":   1150000,
    "MON-27-LG-GP850": 8200000,
    "MON-24-DL-P2422": 3900000,
    "MON-27-SS-LS27":  5500000,
    "CPU-I5-14400":    6300000,
    "CPU-I7-14700K":   12500000,
    "CPU-I9-14900K":   22000000,
    "ACC-THERMAL-MX4": 120000,
    "ACC-FAN-NF-A12":  420000,
}

# Trọng số lựa chọn sản phẩm cho đơn thường (không tính RAM riêng)
PRODUCT_WEIGHTS = {
    "RAM-DDR5-16-KS":  0,    # xử lý riêng
    "RAM-DDR5-32-KS":  8,
    "RAM-DDR5-16-SS":  10,
    "RAM-DDR5-32-CO":  5,
    "SSD-1TB-SS-870":  12,
    "SSD-2TB-SS-870":  4,
    "SSD-512-WD-BL":   10,
    "SSD-1TB-WD-BL":   8,
    "HDD-2TB-SG-BC":   6,
    "HDD-4TB-SG-BC":   3,
    "HDD-2TB-WD-BL":   5,
    "MON-27-LG-GP850": 2,
    "MON-24-DL-P2422": 4,
    "MON-27-SS-LS27":  3,
    "CPU-I5-14400":    4,
    "CPU-I7-14700K":   2,
    "CPU-I9-14900K":   1,
    "ACC-THERMAL-MX4": 6,
    "ACC-FAN-NF-A12":  4,
}


def get_tet_factor(date):
    """Hệ số điều chỉnh Tết Âm lịch 2026."""
    if datetime.date(2026, 1, 20) <= date <= datetime.date(2026, 1, 28):
        days = (date - datetime.date(2026, 1, 20)).days
        return 0.7 - (0.3 * days / 8)
    if datetime.date(2026, 1, 29) <= date <= datetime.date(2026, 2, 5):
        return 0.1
    if datetime.date(2026, 2, 6) <= date <= datetime.date(2026, 2, 15):
        return 1.5
    return 1.0


def get_multiplier(date):
    return DOW_MULT[date.weekday()] * get_tet_factor(date)


def get_ram16ks_target(date, mult):
    """Qty mục tiêu RAM DDR5 16GB Kingston bán trong ngày.

    Bình thường: ~3.5 cái/ngày (distributor B2B nhỏ-vừa).
    Spike từ 31/03: ~57 cái/ngày – rõ ràng bất thường (~16× bình thường).
    Tất cả DOs đều được validate trong seed_finalize → Forecasted = on_hand = 90.
    KB1 scenario detected bằng sales velocity trend (SO history), không phải outgoing_qty.
    """
    if date.weekday() >= 5 and mult < 0.3:
        return random.randint(0, 2)
    if date >= datetime.date(2026, 3, 31):
        base = random.randint(55, 80)   # spike: ~16× bình thường → avg ~57/ngày
    else:
        base = random.randint(2, 5)     # bình thường: ~3.5/ngày
    return max(1, int(base * max(mult, 0.15)))


def pick_other_products(product_ids, n, exclude=None):
    """Chọn n sản phẩm ngẫu nhiên có trọng số, loại trừ exclude."""
    refs = list(PRODUCT_WEIGHTS.keys())
    weights = list(PRODUCT_WEIGHTS.values())
    if exclude:
        filtered = [(r, w) for r, w in zip(refs, weights) if r not in exclude]
        refs, weights = zip(*filtered) if filtered else ([], [])
    if not refs:
        return []
    chosen_refs = []
    remaining = list(zip(refs, weights))
    for _ in range(min(n, len(remaining))):
        r_list, w_list = zip(*remaining)
        pick = random.choices(r_list, weights=w_list, k=1)[0]
        chosen_refs.append(pick)
        remaining = [(r, w) for r, w in remaining if r != pick]
        if not remaining:
            break
    return [(ref, product_ids[ref]) for ref in chosen_refs]


def get_qty_for_product(ref, customer_type):
    """Số lượng cho 1 dòng order tùy loại sản phẩm + khách."""
    if customer_type == "retail":
        if "MON" in ref or "CPU" in ref:
            return random.randint(1, 2)
        return random.randint(1, 5)
    if customer_type == "b2b":
        if "MON" in ref:
            return random.randint(1, 4)
        if "CPU" in ref:
            return random.randint(1, 5)
        if "ACC" in ref:
            return random.randint(2, 10)
        return random.randint(2, 8)   # SSD/HDD/RAM: vừa đủ cho B2B nhỏ-vừa
    # vip (TG PC + IT Solutions): scale về 70-90M nên qty này chỉ là starting point
    if "MON" in ref:
        return random.randint(2, 8)
    if "CPU" in ref:
        return random.randint(2, 8)
    if "ACC" in ref:
        return random.randint(5, 20)
    return random.randint(5, 20)   # SSD/HDD/RAM VIP


def apply_discount(price, customer_type, order_total_est=0):
    """Áp dụng chiết khấu theo loại khách."""
    if customer_type == "vip":
        p = price * 0.95
    elif customer_type == "b2b":
        p = price * 0.97
    else:
        p = price
    if order_total_est > 50_000_000:
        p *= 0.98
    return round(p)


# ═════════════════════════════════════════════════════════════════════════════

def main():
    # ── Xóa SO cũ ──────────────────────────────────────────────────────────
    print("\n=== XÓA SALE ORDERS CŨ ===")
    so_ids = execute("sale.order", "search", [[]])
    if so_ids:
        # 1. Cancel associated pickings first (DOs in non-done/cancel state)
        picking_ids = execute("stock.picking", "search",
                              [[("sale_id", "in", so_ids),
                                ("state", "not in", ["done", "cancel"])]])
        if picking_ids:
            for batch_start in range(0, len(picking_ids), 50):
                batch = picking_ids[batch_start:batch_start + 50]
                try:
                    execute("stock.picking", "action_cancel", batch)
                except Exception:
                    for pid in batch:
                        try:
                            execute("stock.picking", "action_cancel", [pid])
                        except Exception:
                            pass

        # 2. Cancel confirmed SOs in batches of 50
        for batch_start in range(0, len(so_ids), 50):
            batch = so_ids[batch_start:batch_start + 50]
            try:
                execute("sale.order", "action_cancel", batch)
            except Exception:
                for so_id in batch:
                    try:
                        execute("sale.order", "action_cancel", [so_id])
                    except Exception:
                        pass

        # 2b. Force-write state for any still-active SOs
        still_active = execute("sale.order", "search",
                               [[("id", "in", so_ids),
                                 ("state", "not in", ["draft", "cancel"])]])
        if still_active:
            for so_id in still_active:
                try:
                    execute("sale.order", "write", [so_id], {"state": "cancel"})
                except Exception:
                    pass

        # 3. Delete
        try:
            execute("sale.order", "unlink", so_ids)
        except Exception:
            for batch_start in range(0, len(so_ids), 50):
                batch = so_ids[batch_start:batch_start + 50]
                try:
                    execute("sale.order", "unlink", batch)
                except Exception:
                    for so_id in batch:
                        try:
                            execute("sale.order", "unlink", [so_id])
                        except Exception:
                            pass
        print(f"  Đã xóa {len(so_ids)} SO cũ")

    # ── Lookup IDs ──────────────────────────────────────────────────────────
    print("\n=== LOOKUP IDs ===")
    product_ids = {}
    for ref in PRODUCT_DEFS:
        pid = find_product(ref)
        if not pid:
            raise ValueError(f"Product not found: {ref}")
        product_ids[ref] = pid

    # Partners
    cust = {
        "the_gioi_pc":  find_partner("Thế Giới PC"),
        "it_solutions": find_partner("IT Solutions ABC"),
        "hoang_long":   find_partner("Hoàng Long Computer"),
        "minh_khoa":    find_partner("Minh Khoa Tech"),
        "hung_laptop":  find_partner("Hùng Laptop Cần Thơ"),
        "phuc_anh":     find_partner("Phúc Anh"),
        "abc_bd":       find_partner("ABC Computer Bình Dương"),
        "binh":         find_partner("Nguyễn Văn Bình"),
        "mai":          find_partner("Trần Thị Mai"),
        "tuan":         find_partner("Lê Minh Tuấn"),
        "long":         find_partner("Phạm Văn Long"),
    }
    for k, v in cust.items():
        if not v:
            raise ValueError(f"Partner not found: {k}")

    # Salespersons
    khoa_uid = find_user("khoa.sale")
    hang_uid = find_user("hang.sale")

    # Assignment rules
    salesperson_map = {
        "the_gioi_pc": khoa_uid,
        "it_solutions": khoa_uid,
        "hoang_long": hang_uid,
        "minh_khoa": hang_uid,
        "hung_laptop": hang_uid,
    }

    customer_types = {
        "the_gioi_pc": "vip", "it_solutions": "vip",
        "hoang_long": "b2b", "minh_khoa": "b2b", "hung_laptop": "b2b",
        "phuc_anh": "b2b", "abc_bd": "b2b",
        "binh": "retail", "mai": "retail", "tuan": "retail", "long": "retail",
    }

    b2b_keys = ["hoang_long", "minh_khoa", "hung_laptop", "phuc_anh", "abc_bd"]
    retail_keys = ["binh", "mai", "tuan", "long"]

    print("  IDs loaded OK")

    # ── IT Solutions schedule (roughly every 5-7 business days) ─────────────
    it_dates = set()
    d = datetime.date(2026, 1, 7)
    while d <= END_DATE:
        if d.weekday() < 5:
            it_dates.add(d)
        d += datetime.timedelta(days=random.randint(5, 7))
    tg_dates_set = set(TG_PC_DATES)

    # ── Sinh orders ─────────────────────────────────────────────────────────
    print("\n=== TẠO SALE ORDERS ===")
    all_created_ids = []
    id_to_date = {}   # so_id -> date_str (để write-back sau confirm)
    total_lines = 0
    daily_ram16ks = {}  # date -> total qty

    current = START_DATE
    day_count = 0
    while current <= END_DATE:
        mult = get_multiplier(current)
        base_count = random.uniform(3, 6)
        num_orders = max(0, round(base_count * mult))

        # Tet near-zero
        if mult <= 0.1:
            num_orders = random.choices([0, 1], weights=[0.6, 0.4])[0]
        elif num_orders == 0 and mult > 0:
            num_orders = random.choices([0, 1], weights=[0.7, 0.3])[0]

        # RAM target cho ngày
        ram_target = get_ram16ks_target(current, mult)
        ram_allocated = 0

        # Build order list for today
        orders_today = []

        # TG PC order (kịch bản 3)
        if current in tg_dates_set:
            orders_today.append(("the_gioi_pc", True))
            num_orders = max(num_orders, 1)

        # IT Solutions
        if current in it_dates and current not in tg_dates_set:
            orders_today.append(("it_solutions", False))

        # Fill remaining orders with B2B + retail
        remaining = num_orders - len(orders_today)
        for _ in range(max(0, remaining)):
            # 40% B2B, 35% retail, 25% chance extra retail
            r = random.random()
            if r < 0.40:
                key = random.choice(b2b_keys)
            else:
                key = random.choice(retail_keys)
            orders_today.append((key, False))

        # Generate each order
        for cust_key, is_tg_pc_order in orders_today:
            partner_id = cust[cust_key]
            c_type = customer_types[cust_key]
            sp = salesperson_map.get(cust_key, random.choice([khoa_uid, hang_uid]))

            if is_tg_pc_order:
                # TG PC: 4-6 sản phẩm, tổng 70-90M, giá VIP
                n_prods = random.randint(4, 6)
                # Always include RAM DDR5 16GB Kingston
                chosen = [("RAM-DDR5-16-KS", product_ids["RAM-DDR5-16-KS"])]
                others = pick_other_products(product_ids, n_prods - 1,
                                             exclude={"RAM-DDR5-16-KS"})
                chosen.extend(others)

                lines = []
                running_total = 0
                for ref, prod_id in chosen:
                    price = PRODUCT_DEFS[ref]
                    qty = get_qty_for_product(ref, "vip")
                    disc_price = apply_discount(price, "vip", 75_000_000)
                    lines.append((prod_id, qty, disc_price, ref))
                    running_total += qty * disc_price

                # Điều chỉnh để tổng ~70-90M
                target_total = random.randint(70_000_000, 90_000_000)
                if running_total > 0:
                    scale = target_total / running_total
                    for i in range(len(lines)):
                        prod_id, qty, price, ref = lines[i]
                        new_qty = max(1, round(qty * scale))
                        lines[i] = (prod_id, new_qty, price, ref)
            else:
                # Đơn bình thường: 2-4 sản phẩm
                n_prods = random.randint(2, 4)
                # Có thể bao gồm RAM DDR5 16GB Kingston
                include_ram = random.random() < 0.35
                chosen = []
                exclude = set()
                if include_ram:
                    chosen.append(("RAM-DDR5-16-KS", product_ids["RAM-DDR5-16-KS"]))
                    exclude.add("RAM-DDR5-16-KS")
                    n_prods -= 1
                others = pick_other_products(product_ids, n_prods, exclude=exclude)
                chosen.extend(others)

                lines = []
                for ref, prod_id in chosen:
                    price = PRODUCT_DEFS[ref]
                    qty = get_qty_for_product(ref, c_type)
                    disc_price = apply_discount(price, c_type)
                    lines.append((prod_id, qty, disc_price, ref))

                # Check > 50M extra discount
                est_total = sum(q * p for _, q, p, _ in lines)
                if est_total > 50_000_000:
                    lines = [(pid, q, round(p * 0.98), r) for pid, q, p, r in lines]

            # Tính RAM allocated
            for _, qty, _, ref in lines:
                if ref == "RAM-DDR5-16-KS":
                    ram_allocated += qty

            # Tạo order
            order_lines = [(0, 0, {
                "product_id": pid,
                "product_uom_qty": qty,
                "price_unit": price,
            }) for pid, qty, price, _ in lines]

            date_str = f"{current.isoformat()} {random.randint(8,17):02d}:{random.randint(0,59):02d}:00"
            so_id = execute("sale.order", "create", {
                "partner_id": partner_id,
                "date_order": date_str,
                "user_id": sp,
                "order_line": order_lines,
            })
            all_created_ids.append(so_id)
            id_to_date[so_id] = date_str
            total_lines += len(lines)

        # Bổ sung RAM nếu chưa đạt target
        deficit = ram_target - ram_allocated
        if deficit > 0 and num_orders > 0:
            # Tạo thêm 1-2 orders nhỏ chứa RAM
            chunks = [deficit] if deficit <= 30 else [deficit // 2, deficit - deficit // 2]
            for chunk_qty in chunks:
                ckey = random.choice(b2b_keys + retail_keys)
                c_type = customer_types[ckey]
                sp = salesperson_map.get(ckey, random.choice([khoa_uid, hang_uid]))
                price = apply_discount(PRODUCT_DEFS["RAM-DDR5-16-KS"], c_type)

                # Thêm 1-2 sản phẩm khác cho tự nhiên
                extra = pick_other_products(product_ids, random.randint(1, 2),
                                            exclude={"RAM-DDR5-16-KS"})
                ol = [(0, 0, {
                    "product_id": product_ids["RAM-DDR5-16-KS"],
                    "product_uom_qty": chunk_qty,
                    "price_unit": price,
                })]
                for ref, pid in extra:
                    ol.append((0, 0, {
                        "product_id": pid,
                        "product_uom_qty": get_qty_for_product(ref, c_type),
                        "price_unit": apply_discount(PRODUCT_DEFS[ref], c_type),
                    }))

                date_str = f"{current.isoformat()} {random.randint(8,17):02d}:{random.randint(0,59):02d}:00"
                so_id = execute("sale.order", "create", {
                    "partner_id": cust[ckey],
                    "date_order": date_str,
                    "user_id": sp,
                    "order_line": ol,
                })
                all_created_ids.append(so_id)
                id_to_date[so_id] = date_str
                total_lines += 1 + len(extra)
                ram_allocated += chunk_qty

        daily_ram16ks[current] = ram_allocated

        day_count += 1
        if day_count % 10 == 0:
            print(f"  ... ngày {current} ({len(all_created_ids)} orders)")

        current += datetime.timedelta(days=1)

    print(f"  Tạo xong: {len(all_created_ids)} orders, {total_lines} lines")

    # ── Confirm in batches ──────────────────────────────────────────────────
    print("\n=== CONFIRM SALE ORDERS (batch 50) ===")
    for i in range(0, len(all_created_ids), 50):
        batch = all_created_ids[i:i + 50]
        try:
            execute("sale.order", "action_confirm", batch)
        except Exception as e:
            # fallback: confirm one by one
            for sid in batch:
                try:
                    execute("sale.order", "action_confirm", [sid])
                except Exception:
                    pass
        done = min(i + 50, len(all_created_ids))
        print(f"  Confirmed {done}/{len(all_created_ids)}")

    # ── Fix date_order (action_confirm resets it to now) ────────────────────
    print("\n=== FIX date_order sau confirm ===")
    from collections import defaultdict
    date_to_ids = defaultdict(list)
    for oid, ds in id_to_date.items():
        date_to_ids[ds].append(oid)
    fixed = 0
    for ds, ids in sorted(date_to_ids.items()):
        execute("sale.order", "write", ids, {"date_order": ds})
        fixed += len(ids)
    print(f"  Đã fix date_order cho {fixed} orders")

    # ── VERIFY ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("VERIFY RESULTS")
    print("=" * 60)

    total_so = execute("sale.order", "search_count", [[]])
    total_sol = execute("sale.order.line", "search_count", [[]])
    print(f"Tổng orders: {total_so}")
    print(f"Tổng lines : {total_sol}")

    # TG PC
    tg_sos = execute("sale.order", "search_read",
                     [[("partner_id", "=", cust["the_gioi_pc"])]],
                     fields=["date_order"], order="date_order desc")
    print(f"\nThế Giới PC: {len(tg_sos)} đơn")
    if tg_sos:
        print(f"  Đơn cuối: {tg_sos[0]['date_order']}")

    # RAM DDR5 16GB Kingston daily qty
    print("\nRAM DDR5 16GB Kingston – Qty bán theo ngày:")
    print("  Ngày       | Qty")
    print("  -----------|-----")

    ram_march = []
    ram_april = []
    for d_offset in range(-20, 11):
        check_date = datetime.date(2026, 3, 31) + datetime.timedelta(days=d_offset)
        if check_date < datetime.date(2026, 3, 21):
            continue
        qty = daily_ram16ks.get(check_date, 0)
        label = check_date.isoformat()
        print(f"  {label} | {qty}")
        if check_date <= datetime.date(2026, 3, 30):
            ram_march.append(qty)
        else:
            ram_april.append(qty)

    avg_march = sum(ram_march) / len(ram_march) if ram_march else 0
    avg_april = sum(ram_april) / len(ram_april) if ram_april else 0
    all_baseline = [daily_ram16ks.get(START_DATE + datetime.timedelta(days=i), 0)
                    for i in range((datetime.date(2026, 3, 30) - START_DATE).days + 1)]
    mean_bl = sum(all_baseline) / len(all_baseline) if all_baseline else 0
    std_bl = math.sqrt(sum((x - mean_bl) ** 2 for x in all_baseline) / max(len(all_baseline) - 1, 1))
    z_score = (avg_april - mean_bl) / std_bl if std_bl > 0 else 0

    print(f"\n  Avg qty 21-30/03 (baseline): {avg_march:.1f}")
    print(f"  Avg qty 31/03-10/04 (spike): {avg_april:.1f}")
    print(f"  Baseline mean (full): {mean_bl:.1f}, std: {std_bl:.1f}")
    print(f"  Z-score ước tính: {z_score:.1f}")


if __name__ == "__main__":
    main()
