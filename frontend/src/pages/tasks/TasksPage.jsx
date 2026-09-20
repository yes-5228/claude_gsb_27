import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { metaApi } from '../../api/meta.js';
import { taskApi } from '../../api/tasks.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatDateTime } from '../../utils/format.js';

function todayStr() {
  const now = new Date();
  const pad = (num) => String(num).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export default function TasksPage() {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [generating, setGenerating] = useState(false);

  const list = useListQuery(
    (params) => taskApi.list(params),
    { task_date: todayStr(), restroom_id: '', status: '' },
    100,
  );
  const { data: options } = useAsync(() => metaApi.restroomOptions(), []);

  const summary = useMemo(() => {
    const counts = { 待执行: 0, 已完成: 0, 已取消: 0, 漏检: 0 };
    list.items.forEach((item) => {
      counts[item.display_status] = (counts[item.display_status] ?? 0) + 1;
    });
    return counts;
  }, [list.items]);

  const generate = async () => {
    setGenerating(true);
    try {
      const result = await taskApi.generate(list.filters.task_date || todayStr());
      toast.success(
        result.created > 0
          ? `已生成 ${result.created} 条任务，当日共 ${result.total} 条`
          : `任务已存在，无需重复生成（当日共 ${result.total} 条）`,
      );
      list.reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <>
      <PageHeader
        title="巡查任务"
        description="每座开放公厕每日一条巡查任务；公厕停用自动取消，恢复开放自动补回，不重复、不漏项"
        actions={
          <button type="button" className="btn btn-primary" onClick={generate} disabled={generating}>
            {generating ? '生成中…' : '生成当日任务'}
          </button>
        }
      />
      <div className="content">
        <section className="card">
          <div className="filter-bar">
            <Field label="任务日期">
              <input
                type="date"
                value={list.filters.task_date}
                onChange={(event) => list.updateFilter('task_date', event.target.value)}
              />
            </Field>
            <Field label="公厕">
              <select
                value={list.filters.restroom_id}
                onChange={(event) => list.updateFilter('restroom_id', event.target.value)}
              >
                <option value="">全部</option>
                {(options || []).map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.code} {option.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="任务状态">
              <select
                value={list.filters.status}
                onChange={(event) => list.updateFilter('status', event.target.value)}
              >
                <option value="">全部</option>
                {(dictionaries?.inspection_task_status || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <button type="button" className="btn" onClick={list.resetFilters}>
              重置
            </button>
            <span className="hint" style={{ alignSelf: 'center' }}>
              待执行 {summary.待执行} · 已完成 {summary.已完成} · 已取消 {summary.已取消} · 漏检{' '}
              {summary.漏检}
            </span>
          </div>
        </section>

        <section className="card">
          <DataTable
            loading={list.loading}
            error={list.error}
            rows={list.items}
            emptyText="当日暂无巡查任务，可点击右上角生成"
            columns={[
              {
                key: 'restroom',
                title: '公厕',
                render: (row) =>
                  row.restroom ? (
                    <Link to={`/restrooms/${row.restroom_id}`}>
                      {row.restroom.name}（{row.restroom.code}）
                    </Link>
                  ) : (
                    '-'
                  ),
              },
              { key: 'task_date', title: '任务日期' },
              {
                key: 'display_status',
                title: '状态',
                render: (row) => <StatusTag status={row.display_status} />,
              },
              {
                key: 'inspection_id',
                title: '关联巡查',
                render: (row) => (row.inspection_id ? `巡查 #${row.inspection_id}` : '-'),
              },
              {
                key: 'cancel_reason',
                title: '取消原因',
                wrap: true,
                render: (row) => row.cancel_reason || '-',
              },
              {
                key: 'completed_at',
                title: '完成时间',
                render: (row) => formatDateTime(row.completed_at),
              },
              {
                key: 'generated_at',
                title: '生成时间',
                render: (row) => formatDateTime(row.generated_at),
              },
            ]}
          />
          <Pagination meta={list.meta} onPageChange={list.setPage} />
        </section>
      </div>
    </>
  );
}
