from pydantic import Field

field_symbol = Field(description="股票代码")

field_market = Field(
    "sh",
    description="市场: sh=沪市, sz=深市, bj=北交所, hk=港股, us=美股"
)
