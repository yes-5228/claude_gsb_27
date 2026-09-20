import { useState } from 'react';

import { restroomApi } from '../../api/restrooms.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';

const LINKAGE_HINTS = {
  维修中: '变更后：不再生成新的巡查任务，待执行任务自动取消；未闭环问题按生效中的顺延规则顺延期限并说明原因。',
  暂停使用: '变更后：不再生成新的巡查任务，待执行任务自动取消；未闭环问题按生效中的顺延规则顺延期限并说明原因。',
  正常开放: '变更后：恢复生成巡查任务，此前因停用取消的任务自动补回；停用期间的空白不计入漏检。',
};

export default function RestroomStatusModal({ restroom, onClose, onChanged }) {
  const { dictionaries } = useDictionaries();
  const [form, setForm] = useState({ to_status: '', reason: '', operator: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const options = (dictionaries?.restroom_status || []).filter(
    (item) => item !== restroom.status,
  );

  const submit = async (event) => {
    event.preventDefault();
    if (!form.to_status) {
      setError('请选择目标状态');
      return;
    }
    if (!form.reason.trim() || !form.operator.trim()) {
      setError('变更原因与操作人为必填项');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await restroomApi.changeStatus(restroom.id, {
        to_status: form.to_status,
        reason: form.reason.trim(),
        operator: form.operator.trim(),
      });
      onChanged(result);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`状态变更 - ${restroom.name}`}
      onClose={onClose}
      width={560}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="status-form" className="btn btn-primary" disabled={saving}>
            {saving ? '提交中…' : '确认变更'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="status-form" className="form-grid" onSubmit={submit}>
        <Field label="当前状态">
          <div style={{ paddingTop: 6 }}>
            <StatusTag status={restroom.status} />
          </div>
        </Field>
        <Field label="目标状态 *">
          <select
            value={form.to_status}
            onChange={(event) => setForm((prev) => ({ ...prev, to_status: event.target.value }))}
          >
            <option value="">请选择</option>
            {options.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </Field>
        <Field label="变更原因 *" full>
          <textarea
            rows="2"
            value={form.reason}
            onChange={(event) => setForm((prev) => ({ ...prev, reason: event.target.value }))}
            placeholder="如：化粪池检修，预计停用 3 天"
          />
        </Field>
        <Field label="操作人 *">
          <input
            value={form.operator}
            onChange={(event) => setForm((prev) => ({ ...prev, operator: event.target.value }))}
            placeholder="请输入操作人姓名"
          />
        </Field>
      </form>
      {form.to_status ? (
        <div className="alert alert-info" style={{ marginTop: 12 }}>
          {LINKAGE_HINTS[form.to_status]}
        </div>
      ) : null}
    </Modal>
  );
}
