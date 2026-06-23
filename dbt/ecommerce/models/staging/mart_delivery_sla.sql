with orders as (
    select * from {{ ref('int_orders_enriched') }}
    where order_status = 'delivered'
)
select
    date_trunc('month', purchased_at)  as month,
    count(order_id)                    as total_delivered,
    sum(case when is_late_delivery then 1 else 0 end) as late_deliveries,
    round(
        100.0 * sum(case when is_late_delivery then 1 else 0 end) / count(order_id),
        2
    )                                  as late_delivery_pct,
    avg(delivery_delay_days)           as avg_delay_days
from orders
group by 1
order by 1