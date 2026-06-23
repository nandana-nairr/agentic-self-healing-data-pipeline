with source as (
    select * from {{ source('olist', 'raw_order_items') }}
),
renamed as (
    select
        order_id,
        order_item_id,
        product_id,
        seller_id,
        price::numeric(10,2)                   as price,
        freight_value::numeric(10,2)            as freight_value,
        (price + freight_value)::numeric(10,2)  as total_value
    from source
)
select * from renamed