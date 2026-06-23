with orders as (
    select * from {{ ref('stg_orders') }}
),
items as (
    select
        order_id,
        sum(price)         as total_price,
        sum(freight_value) as total_freight,
        count(*)           as item_count
    from {{ ref('stg_order_items') }}
    group by order_id
),
payments as (
    select
        order_id,
        sum(payment_value) as total_payment
    from {{ ref('stg_payments') }}
    group by order_id
)
select
    o.order_id,
    o.customer_id,
    o.order_status,
    o.purchased_at,
    o.delivered_at,
    o.estimated_delivery_at,
    i.total_price,
    i.total_freight,
    i.item_count,
    p.total_payment,
    case
        when o.delivered_at > o.estimated_delivery_at then true
        else false
    end as is_late_delivery,
    extract(day from (o.delivered_at - o.estimated_delivery_at)) as delivery_delay_days
from orders o
left join items i on o.order_id = i.order_id
left join payments p on o.order_id = p.order_id