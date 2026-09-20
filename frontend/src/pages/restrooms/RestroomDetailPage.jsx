import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { inspectionApi } from '../../api/inspections.js';
import { issueApi } from '../../api/issues.js';
import { restroomApi } from '../../api/restrooms.js';
import DataTable from '../../components/DataTable.jsx';
import DetailList from '../../components/DetailList.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { ScorePill, SeverityTag, StatusTag } from '../../components/Tags.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatDateTime } from '../../utils/format.js';
import RestroomFormModal from './RestroomFormModal.jsx';
import RestroomStatusModal from './RestroomStatusModal.jsx';

const TABS = [
  { key: 'profile', label: '基础档案' },
  { key: 'inspections', label: '巡查记录' },
  { key: 'issues', label: '问题记录' },
  { key: 'status', label: '状态记录' },
];

export default function RestroomDetailPage() {
  const { restroomId } = useParams();
  const [tab, setTab] = useState('profile');
  const [showForm, setShowForm] = useState(false);
  const [showStatus, setShowStatus] = useState(false);

  const { data: restroom, loading, error, reload } = useAsync(
    () => restroomApi.detail(restroomId),
    [restroomId],
  );
  const inspections = useListQuery(
    (params) => inspectionApi.list({ ...params, restroom_id: restroomId }),
    {},
    5,
  );
  const issues = useListQuery(
    (params) => issueApi.list({ ...params, restroom_id: restroomId }),
    {},
    5,
  );
  const statusEvents = useAsync(
    () => (tab === 'status' ? restroomApi.statusEvents(restroomId) : Promise.resolve(null)),
    [restroomId, tab],
  );
  const suspensions = useAsync(
    () => (tab === 'status' ? restroomApi.suspensions(restroomId) : Promise.resolve(null)),
    [restroomId, tab],
  );

  return (
    <>
      <PageHeader
        title={restroom ? `${restroom.name}（${restroom.code}）` : '公厕详情'}
        description={restroom ? `${restroom.district} · ${restroom.address}` : '加载中…'}
        actions={
          <>
            <Link className="btn" to="/restrooms">
              返回列表
            </Link>
            <button type="button" className="btn" onClick={() => setShowStatus(true)}>
              变更状态
            </button>
            <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
              编辑档案
            </button>
          </>
        }
      />
      <div className="content">
        {error ? <div className="alert alert-error">{error.message}</div> : null}
        {loading && !restroom ? <div className="loading-block">加载中…</div> : null}

        {restroom ? (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="label">累计巡查</div>
                <div className="value">
                  {restroom.inspection_count}
                  <span className="unit">次</span>
                </div>
                <div className="foot">
                  最近巡查：{formatDateTime(restroom.latest_inspection_time)}
                </div>
              </div>
              <div className="stat-card is-info">
                <div className="label">巡查均分</div>
                <div className="value">
                  {restroom.avg_score != null ? restroom.avg_score.toFixed(1) : '-'}
                  <span className="unit">分</span>
                </div>
                <div className="foot">
                  最近得分：{restroom.latest_inspection_score ?? '-'}
                </div>
              </div>
              <div className={`stat-card${restroom.open_issue_count ? ' is-danger' : ''}`}>
                <div className="label">未闭环问题</div>
                <div className="value">
                  {restroom.open_issue_count}
                  <span className="unit">条</span>
                </div>
                <div className="foot">累计上报 {restroom.total_issue_count} 条</div>
              </div>
            </div>

            <div className="inline">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`btn btn-sm${tab === item.key ? ' btn-primary' : ''}`}
                  onClick={() => setTab(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {tab === 'profile' ? (
              <section className="card">
                <div className="card-title">
                  <h3>基础档案</h3>
                </div>
                <DetailList
                  items={[
                    { label: '公厕编号', value: restroom.code },
                    { label: '公厕名称', value: restroom.name },
                    { label: '所属区域', value: restroom.district },
                    { label: '详细地址', value: restroom.address },
                    { label: '公厕等级', value: restroom.grade },
                    { label: '开放状态', value: <StatusTag status={restroom.status} /> },
                    { label: '开放时间', value: restroom.open_hours },
                    { label: '保洁责任人', value: restroom.manager },
                    { label: '联系电话', value: restroom.manager_phone },
                    { label: '蹲位数量', value: `${restroom.stall_count} 个` },
                    { label: '洗手盆数量', value: `${restroom.basin_count} 个` },
                    { label: '无障碍设施', value: restroom.has_accessible ? '已配置' : '未配置' },
                    { label: '备注', value: restroom.remark || '无' },
                    { label: '建档时间', value: formatDateTime(restroom.created_at) },
                  ]}
                />
              </section>
            ) : null}

            {tab === 'inspections' ? (
              <section className="card">
                <div className="card-title">
                  <h3>巡查记录</h3>
                  <Link className="hint" to="/inspections">
                    前往巡查模块 →
                  </Link>
                </div>
                <DataTable
                  loading={inspections.loading}
                  error={inspections.error}
                  rows={inspections.items}
                  emptyText="该公厕暂无巡查记录"
                  columns={[
                    { key: 'inspect_time', title: '巡查时间', render: (row) => formatDateTime(row.inspect_time) },
                    { key: 'inspector', title: '巡查人' },
                    { key: 'shift', title: '班次' },
                    { key: 'score', title: '得分', render: (row) => <ScorePill score={row.score} /> },
                    { key: 'result', title: '结论', render: (row) => <StatusTag status={row.result} /> },
                    { key: 'remark', title: '备注', wrap: true, render: (row) => row.remark || '-' },
                  ]}
                />
                <Pagination meta={inspections.meta} onPageChange={inspections.setPage} />
              </section>
            ) : null}

            {tab === 'issues' ? (
              <section className="card">
                <div className="card-title">
                  <h3>问题记录</h3>
                  <Link className="hint" to="/issues">
                    前往整改模块 →
                  </Link>
                </div>
                <DataTable
                  loading={issues.loading}
                  error={issues.error}
                  rows={issues.items}
                  emptyText="该公厕暂无问题上报"
                  columns={[
                    { key: 'code', title: '编号' },
                    {
                      key: 'title',
                      title: '问题',
                      wrap: true,
                      render: (row) => <Link to={`/issues/${row.id}`}>{row.title}</Link>,
                    },
                    { key: 'category', title: '分类' },
                    { key: 'severity', title: '程度', render: (row) => <SeverityTag severity={row.severity} /> },
                    { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
                    { key: 'report_time', title: '上报时间', render: (row) => formatDateTime(row.report_time) },
                  ]}
                />
                <Pagination meta={issues.meta} onPageChange={issues.setPage} />
              </section>
            ) : null}

            {tab === 'status' ? (
              <>
                <section className="card">
                  <div className="card-title">
                    <h3>状态变更留痕</h3>
                    <span className="hint">停用与恢复均记录</span>
                  </div>
                  <DataTable
                    loading={statusEvents.loading}
                    error={statusEvents.error}
                    rows={statusEvents.data || []}
                    emptyText="暂无状态变更记录"
                    columns={[
                      { key: 'created_at', title: '变更时间', render: (row) => formatDateTime(row.created_at) },
                      { key: 'from_status', title: '原状态', render: (row) => <StatusTag status={row.from_status} /> },
                      { key: 'to_status', title: '新状态', render: (row) => <StatusTag status={row.to_status} /> },
                      { key: 'operator', title: '操作人', render: (row) => row.operator || '-' },
                      { key: 'reason', title: '变更原因', wrap: true, render: (row) => row.reason || '-' },
                    ]}
                  />
                </section>

                <section className="card">
                  <div className="card-title">
                    <h3>停用区间</h3>
                    <span className="hint">停用期间不计入漏巡</span>
                  </div>
                  <DataTable
                    loading={suspensions.loading}
                    error={suspensions.error}
                    rows={suspensions.data || []}
                    emptyText="暂无停用记录"
                    columns={[
                      { key: 'started_at', title: '停用开始', render: (row) => formatDateTime(row.started_at) },
                      {
                        key: 'ended_at',
                        title: '恢复开放',
                        render: (row) => (row.ended_at ? formatDateTime(row.ended_at) : '停用中'),
                      },
                      {
                        key: 'extend_days',
                        title: '期限顺延',
                        render: (row) =>
                          row.extend_days == null
                            ? '不顺延'
                            : row.extend_days === 0
                              ? '按停用时长顺延'
                              : `固定顺延 ${row.extend_days} 天`,
                      },
                      {
                        key: 'extension_settled',
                        title: '顺延结算',
                        render: (row) =>
                          row.extend_days == null ? '-' : row.extension_settled ? '已结算' : '待恢复结算',
                      },
                      { key: 'reason', title: '停用原因', wrap: true, render: (row) => row.reason || '-' },
                    ]}
                  />
                </section>
              </>
            ) : null}
          </>
        ) : null}
      </div>

      {showForm && restroom ? (
        <RestroomFormModal
          restroom={restroom}
          onClose={() => setShowForm(false)}
          onSaved={reload}
        />
      ) : null}

      {showStatus && restroom ? (
        <RestroomStatusModal
          restroom={restroom}
          onClose={() => setShowStatus(false)}
          onChanged={() => {
            reload();
            statusEvents.reload();
            suspensions.reload();
          }}
        />
      ) : null}
    </>
  );
}
