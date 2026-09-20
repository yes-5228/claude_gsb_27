import { useState } from 'react';
import { Link } from 'react-router-dom';

import { assessmentApi } from '../../api/assessments.js';
import { ruleApi } from '../../api/rules.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { GradeTag, ScorePill } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatDateTime, toDateTimeInput } from '../../utils/format.js';

const TABS = [
  { key: 'assessments', label: '月度考核' },
  { key: 'rules', label: '期限顺延规则' },
];

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

const EMPTY_RULE = {
  name: '',
  extend_days: 3,
  trigger_statuses: ['维修中', '暂停使用'],
  effective_from: toDateTimeInput(),
  enabled: true,
  remark: '',
};

function RuleFormModal({ onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY_RULE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const toggleStatus = (status) => {
    setForm((prev) => ({
      ...prev,
      trigger_statuses: prev.trigger_statuses.includes(status)
        ? prev.trigger_statuses.filter((item) => item !== status)
        : [...prev.trigger_statuses, status],
    }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('请填写规则名称');
      return;
    }
    if (!form.trigger_statuses.length) {
      setError('至少选择一个触发状态');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await ruleApi.create({
        ...form,
        extend_days: Number(form.extend_days),
        effective_from: new Date(form.effective_from).toISOString(),
        remark: form.remark || null,
      });
      toast.success('顺延规则已创建，仅对生效时间之后的判定生效');
      onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="新增顺延规则"
      onClose={onClose}
      width={560}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="rule-form" className="btn btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="rule-form" className="form-grid" onSubmit={submit}>
        <Field label="规则名称 *">
          <input
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="如：停用顺延规则"
          />
        </Field>
        <Field label="每次停用顺延天数">
          <input
            type="number"
            min="0"
            max="365"
            value={form.extend_days}
            onChange={(event) => setForm((prev) => ({ ...prev, extend_days: event.target.value }))}
          />
        </Field>
        <Field label="触发状态" full>
          <div className="inline">
            {['维修中', '暂停使用'].map((status) => (
              <label key={status} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={form.trigger_statuses.includes(status)}
                  onChange={() => toggleStatus(status)}
                />
                {status}
              </label>
            ))}
          </div>
        </Field>
        <Field label="生效时间" hint="只影响该时间之后的状态判定，不影响历史">
          <input
            type="datetime-local"
            value={form.effective_from}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, effective_from: event.target.value }))
            }
          />
        </Field>
        <Field label="是否启用">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, enabled: event.target.checked }))
              }
            />
            启用
          </label>
        </Field>
        <Field label="规则说明" full>
          <textarea
            rows="2"
            value={form.remark}
            onChange={(event) => setForm((prev) => ({ ...prev, remark: event.target.value }))}
          />
        </Field>
      </form>
    </Modal>
  );
}

function AssessmentsPanel() {
  const toast = useToast();
  const [generating, setGenerating] = useState(false);
  const list = useListQuery(
    (params) => assessmentApi.list(params),
    { month: currentMonth() },
    100,
  );

  const generate = async () => {
    if (!list.filters.month) {
      toast.error('请先选择考核月份');
      return;
    }
    setGenerating(true);
    try {
      const result = await assessmentApi.generate(list.filters.month, '值班长');
      toast.success(
        result.created > 0
          ? `已生成 ${result.created} 座公厕的考核快照`
          : `该月份考核已全部生成（跳过 ${result.skipped} 座），已发布的考核不再变化`,
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
      <section className="card">
        <div className="filter-bar">
          <Field label="考核月份">
            <input
              type="month"
              value={list.filters.month}
              onChange={(event) => list.updateFilter('month', event.target.value)}
            />
          </Field>
          <button type="button" className="btn btn-primary" onClick={generate} disabled={generating}>
            {generating ? '生成中…' : '生成该月考核'}
          </button>
          <span className="hint" style={{ alignSelf: 'center' }}>
            考核按「应巡天数、漏检天数、巡查均分」计算快照；已生成的考核不随后续状态变化改变
          </span>
        </div>
      </section>
      <section className="card">
        <DataTable
          loading={list.loading}
          error={list.error}
          rows={list.items}
          emptyText="该月份暂无考核数据，点击上方按钮生成"
          columns={[
            {
              key: 'restroom',
              title: '公厕',
              render: (row) =>
                row.restroom ? (
                  <Link to={`/restrooms/${row.restroom_id}`}>{row.restroom.name}</Link>
                ) : (
                  '-'
                ),
            },
            { key: 'month', title: '月份' },
            { key: 'expected_count', title: '应巡(天)' },
            { key: 'actual_count', title: '实巡(次)' },
            {
              key: 'missed_count',
              title: '漏检(天)',
              render: (row) =>
                row.missed_count > 0 ? (
                  <span className="tag tag-danger">{row.missed_count}</span>
                ) : (
                  0
                ),
            },
            {
              key: 'avg_score',
              title: '巡查均分',
              render: (row) => (row.avg_score != null ? <ScorePill score={row.avg_score} /> : '-'),
            },
            { key: 'issue_new', title: '新增问题' },
            { key: 'issue_closed', title: '闭环问题' },
            { key: 'score', title: '考核得分' },
            { key: 'result', title: '结果', render: (row) => <GradeTag grade={row.result} /> },
            {
              key: 'generated_at',
              title: '生成时间',
              render: (row) => formatDateTime(row.generated_at),
            },
          ]}
        />
        <Pagination meta={list.meta} onPageChange={list.setPage} />
      </section>
    </>
  );
}

function RulesPanel() {
  const toast = useToast();
  const [showForm, setShowForm] = useState(false);
  const { data: rules, loading, error, reload } = useAsync(() => ruleApi.list(), []);

  const toggleEnabled = async (rule) => {
    try {
      await ruleApi.update(rule.id, { enabled: !rule.enabled });
      toast.success(rule.enabled ? `规则「${rule.name}」已停用` : `规则「${rule.name}」已启用`);
      reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <section className="card">
      <div className="card-title">
        <h3>整改期限顺延规则</h3>
        <button type="button" className="btn btn-sm btn-primary" onClick={() => setShowForm(true)}>
          + 新增规则
        </button>
      </div>
      <p className="hint" style={{ margin: '0 0 12px' }}>
        公厕转入维修中/暂停使用时，按生效中的规则顺延未闭环问题的整改期限并写入整改流水；规则带生效时间，只影响此后的判定。
      </p>
      <DataTable
        loading={loading}
        error={error}
        rows={rules || []}
        rowKey={(row) => row.id}
        emptyText="暂无顺延规则"
        columns={[
          { key: 'name', title: '规则名称' },
          { key: 'extend_days', title: '顺延天数', render: (row) => `${row.extend_days} 天/次` },
          {
            key: 'trigger_statuses',
            title: '触发状态',
            render: (row) => (row.trigger_statuses || []).join('、'),
          },
          {
            key: 'effective_from',
            title: '生效时间',
            render: (row) => formatDateTime(row.effective_from),
          },
          {
            key: 'enabled',
            title: '状态',
            render: (row) => (
              <span className={`tag ${row.enabled ? 'tag-success' : 'tag-neutral'}`}>
                {row.enabled ? '启用中' : '已停用'}
              </span>
            ),
          },
          { key: 'remark', title: '说明', wrap: true, render: (row) => row.remark || '-' },
          {
            key: 'actions',
            title: '操作',
            render: (row) => (
              <button type="button" className="btn-link" onClick={() => toggleEnabled(row)}>
                {row.enabled ? '停用' : '启用'}
              </button>
            ),
          },
        ]}
      />
      {showForm ? <RuleFormModal onClose={() => setShowForm(false)} onSaved={reload} /> : null}
    </section>
  );
}

export default function AssessmentsPage() {
  const [tab, setTab] = useState('assessments');

  return (
    <>
      <PageHeader
        title="月度考核"
        description="按自然月生成公厕保洁考核快照，并维护整改期限顺延规则"
      />
      <div className="content">
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
        {tab === 'assessments' ? <AssessmentsPanel /> : <RulesPanel />}
      </div>
    </>
  );
}
