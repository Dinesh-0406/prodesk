import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ClientPicker } from "../../components/ClientPicker";
import { FileDrop } from "../../components/FileDrop";
import { Button, ErrorBox, Input, Modal, Select } from "../../components/ui";
import { useToast } from "../../hooks/useToast";
import { errorMessage } from "../../services/api";
import { documentApi } from "../../services/endpoints";
import type { Doc } from "../../types";
import { DOCUMENT_TYPES, financialYears } from "../../utils/format";

export function UploadDocumentModal({
  open,
  onClose,
  clientId,
  onUploaded,
}: {
  open: boolean;
  onClose: () => void;
  clientId?: string;
  onUploaded?: (d: Doc) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [client, setClient] = useState(clientId ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState("ITR_ACKNOWLEDGEMENT");
  const [fy, setFy] = useState(financialYears()[1]);
  const [desc, setDesc] = useState("");

  const m = useMutation({
    mutationFn: () =>
      documentApi.upload({
        file: file as File,
        client_id: client,
        document_type: type,
        financial_year: fy || undefined,
        description: desc || undefined,
      }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["client-summary"] });
      toast("success", `Uploaded ${d.file_name} successfully`);
      setFile(null);
      setDesc("");
      onUploaded?.(d);
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Upload Document"
      subtitle="Store in private vault with version control & checksum"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!file || !client} loading={m.isPending} onClick={() => m.mutate()} className="shadow-sm">
            Upload
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {m.error && <ErrorBox error={new Error(errorMessage(m.error))} />}

        {!clientId && <ClientPicker value={client} onChange={setClient} />}

        <FileDrop file={file} onFile={setFile} />

        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Document type"
            options={DOCUMENT_TYPES}
            value={type}
            onChange={(e) => setType(e.target.value)}
          />
          <Select
            label="Financial year"
            placeholder="Not applicable"
            options={financialYears(8)}
            value={fy}
            onChange={(e) => setFy(e.target.value)}
          />
        </div>

        <Input
          label="Description (optional)"
          placeholder="e.g. Revised return acknowledgment with refund"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
        />

        <p className="rounded-lg bg-ink-50/70 border border-ink-100 p-2.5 text-xs text-ink-500">
          Files are encrypted and stored in your firm's private vault. Clients only receive access after a partner reviews and signs off on the document.
        </p>
      </div>
    </Modal>
  );
}
