import { useState } from 'react';

import { restroomApi } from '../../api/restrooms.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';

// 与后端 RESTROOM_STATUS_TRANSITIONS 保持一致
const TRANSITIONS = {
  正常开放: ['维修中', '暂停使用'],
  维修中: ['正常开放', '暂停使用'],
  暂停使用: ['正常开放', '维修中'],
};

const SUSPENDED = ['维修中', '暂停使用'];

export default function RestroomStatusModal({ restroom, onClose, onChanged }) {
  const toast = useToast();
  const options = TRANSITIONS[restroom.status] || [];
  const [toStatus, setToStatus] = useState(options[0] || '');
  const [reason, setReason] = useState('');
  const [operator, setOperator] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const suspending = SUSPENDED.includes(toStatus);

  const submit = async (event) => {
    event.preventDefault();
    if (!toStatus) return;
    setSaving(true);
    setError(null);
    try {
      const result = await restroomApi.changeStatus(restroom.id, {
        to_status: toStatus,
        reason: reason || null,
        operator,
      });
      toast.success(result.message || '状态已变更');
      onChanged();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`变更开放状态 - ${restroom.name}`}
      onClose={onClose}
      width={560}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="restroom-status-form" className="btn btn-primary" disabled={saving}>
            {saving ? '提交中…' : '确认变更'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="restroom-status-form" className="form-grid" onSubmit={submit}>
        <Field label="当前状态">
          <input value={restroom.status} disabled />
        </Field>
        <Field label="变更为 *">
          <select value={toStatus} onChange={(event) => setToStatus(event.target.value)}>
            {options.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </Field>
        <Field label="操作人">
          <input
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            placeholder="值班长 / 管理员"
          />
        </Field>
        <Field label="变更原因" full hint={suspending ? '停用后将不再生成新的巡查任务' : '恢复后按规则结算整改期限顺延'}>
          <textarea
            rows="2"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={suspending ? '如：水管爆裂检修' : '如：维修完成恢复开放'}
          />
        </Field>
      </form>
    </Modal>
  );
}
