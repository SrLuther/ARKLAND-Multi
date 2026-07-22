import sys, os, tempfile
sys.path.insert(0, os.path.join(os.getcwd(), 'plugin', 'arkshop_web'))
import app as a
from sqlalchemy import text

p = tempfile.TemporaryDirectory()
url = 'sqlite:///' + os.path.join(p.name, 'test.db')
a._configure_database(url)
a.Base.metadata.create_all(bind=a._ENGINE)
with a._ENGINE.connect() as conn:
    conn.execute(text('CREATE TABLE IF NOT EXISTS players (steam_id VARCHAR(20) PRIMARY KEY NOT NULL, points INTEGER NOT NULL DEFAULT 0, kits TEXT DEFAULT "{}")'))
    conn.commit()

orig_read = a._read_shop_config
try:
    a._read_shop_config = lambda: {
        'Items': {
            'licenca_gamma': {
                'Type': 'license',
                'Description': 'Licença Gamma (30 dias)',
            }
        },
        'Kits': {},
    }
    a._invalidate_shop_config_cache()
    sid = '76561198000000002'
    db = a._SessionLocal()
    try:
        o = a.Order(
            order_id='oid', steam_id=sid, server_id='default', item_type='shop', item_id='licenca_gamma',
            amount=1, points_spent=0, status='PENDENTE', created_at=a._now(), updated_at=a._now(),
        )
        db.add(o)
        db.commit()
    finally:
        db.close()
    a._get_player_entitlements = lambda sid: [{'group': 'Gamma', 'source': 'oid', 'expires_at': '2099-01-01T00:00:00+00:00'}] if sid == '76561198000000002' else []
    db = a._SessionLocal()
    try:
        order = db.query(a.Order).filter(a.Order.order_id == 'oid').first()
        print('order before', order.status)
        print('group', a._order_license_group(order))
        print('already_fulfilled', a._order_license_already_fulfilled(order))
        print('finalize', a._finalize_license_order_if_fulfilled(db, order, reason='test', deferred_perm_syncs=[]))
        print('order after', order.status, order.last_error)
        db.commit()
        order2 = db.query(a.Order).filter(a.Order.order_id == 'oid').first()
        print('order after commit', order2.status)
    finally:
        db.close()
finally:
    a._read_shop_config = orig_read
