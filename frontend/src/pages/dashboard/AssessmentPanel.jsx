import { useState } from 'react';

import { statsApi } from '../../api/stats.js';
import DataTable from '../../components/DataTable.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { formatDateTime } from '../../utils/format.js';

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export default function AssessmentPanel() {
  const toast = useToast();
  const [month, setMonth] = useState(currentMonth());
  const [generating, setGenerating] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () => statsApi.assessments({ year_month: month }),
    [month],
  );

  const generate = async () => {
    setGenerating(true);
    try {
      const result = await statsApi.generateAssessments(month);
      toast.success(result.message);
      reload();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <section className="card">
      <div className="card-title">
        <h3>月度考核</h3>
        <div className="inline">
          <input
            type="month"
            value={month}
            onChange={(event) => setMonth(event.target.value)}
            style={{ maxWidth: 160 }}
          />
          <button type="button" className="btn btn-sm" onClick={generate} disabled={generating}>
            {generating ? '生成中…' : '生成考核'}
          </button>
        </div>
      </div>
      <div className="hint" style={{ marginBottom: 8 }}>
        生成后冻结，后续状态变化与期限顺延不回溯；停用期间不计入应巡。
      </div>
      <DataTable
        loading={loading}
        error={error}
        rows={data || []}
        emptyText="该月份尚未生成考核，点击右上角「生成考核」"
        columns={[
          { key: 'restroom_name', title: '公厕', wrap: true },
          { key: 'district', title: '区域' },
          { key: 'open_days', title: '开放天数' },
          { key: 'expected_inspections', title: '应巡' },
          { key: 'actual_inspections', title: '实巡' },
          {
            key: 'missed_inspections',
            title: '漏巡',
            render: (row) =>
              row.missed_inspections > 0 ? (
                <span className="tag tag-danger">{row.missed_inspections}</span>
              ) : (
                0
              ),
          },
          {
            key: 'avg_score',
            title: '均分',
            render: (row) => (row.avg_score != null ? row.avg_score.toFixed(1) : '-'),
          },
          { key: 'issue_reported', title: '上报问题' },
          { key: 'issue_closed', title: '闭环问题' },
          { key: 'generated_at', title: '生成时间', render: (row) => formatDateTime(row.generated_at) },
        ]}
      />
    </section>
  );
}
