"""公厕台账相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import RestroomGrade, RestroomStatus


class RestroomBrief(BaseModel):
    """其他模块引用公厕时的精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    district: str
    address: str = ""


class RestroomBase(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="公厕名称")
    district: str = Field(min_length=1, max_length=60, description="所属区域")
    address: str = Field(default="", max_length=200, description="详细地址")
    grade: RestroomGrade = Field(default=RestroomGrade.SECOND, description="公厕等级")
    status: RestroomStatus = Field(default=RestroomStatus.NORMAL, description="开放状态")
    manager: str = Field(default="", max_length=60, description="保洁责任人")
    manager_phone: str = Field(default="", max_length=30, description="联系电话")
    open_hours: str = Field(default="06:00-22:00", max_length=60, description="开放时间")
    stall_count: int = Field(default=0, ge=0, description="蹲位数量")
    basin_count: int = Field(default=0, ge=0, description="洗手盆数量")
    has_accessible: bool = Field(default=True, description="是否有无障碍设施")
    longitude: float | None = Field(default=None, description="经度")
    latitude: float | None = Field(default=None, description="纬度")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class RestroomCreate(RestroomBase):
    code: str | None = Field(default=None, max_length=32, description="公厕编号，留空自动生成")


class RestroomUpdate(BaseModel):
    """局部更新，仅提交需要变更的字段。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    district: str | None = Field(default=None, min_length=1, max_length=60)
    address: str | None = Field(default=None, max_length=200)
    grade: RestroomGrade | None = None
    status: RestroomStatus | None = None
    manager: str | None = Field(default=None, max_length=60)
    manager_phone: str | None = Field(default=None, max_length=30)
    open_hours: str | None = Field(default=None, max_length=60)
    stall_count: int | None = Field(default=None, ge=0)
    basin_count: int | None = Field(default=None, ge=0)
    has_accessible: bool | None = None
    longitude: float | None = None
    latitude: float | None = None
    remark: str | None = Field(default=None, max_length=500)


class RestroomOut(RestroomBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    created_at: datetime
    updated_at: datetime


class RestroomDetail(RestroomOut):
    """台账详情，附带巡查与问题的汇总信息。"""

    inspection_count: int = 0
    latest_inspection_time: datetime | None = None
    latest_inspection_score: float | None = None
    avg_score: float | None = None
    open_issue_count: int = 0
    total_issue_count: int = 0
    status_changed_at: datetime | None = Field(default=None, description="最近一次状态变更时间")


class RestroomStatusChange(BaseModel):
    """一次开放状态变更操作，会联动巡查任务与整改期限。"""

    to_status: RestroomStatus = Field(description="目标状态")
    reason: str = Field(min_length=1, max_length=500, description="变更原因")
    operator: str = Field(min_length=1, max_length=60, description="操作人")


class RestroomStatusEventOut(BaseModel):
    """状态变更流水节点。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    from_status: str
    to_status: str
    reason: str
    operator: str
    created_at: datetime


class RestroomStatusChangeResult(BaseModel):
    """状态变更的联动结果汇总。"""

    restroom: RestroomOut
    event: RestroomStatusEventOut
    cancelled_tasks: int = Field(default=0, description="本次取消的待执行任务数")
    revived_tasks: int = Field(default=0, description="本次恢复的待执行任务数")
    extended_issues: int = Field(default=0, description="本次顺延期限的未闭环问题数")
    applied_rule: str | None = Field(default=None, description="命中的顺延规则名称")
