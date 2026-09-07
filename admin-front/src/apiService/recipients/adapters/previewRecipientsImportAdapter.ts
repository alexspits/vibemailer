import type {
  ImportPreview,
  ImportPreviewResponseWire,
  PreviewRecipientsImportInput,
  RecipientsImportTextWire,
} from '../recipientsApiTypes';

const previewRecipientsImportAdapter = {
  adaptParams: (input: PreviewRecipientsImportInput): RecipientsImportTextWire => ({
    text: input.text,
  }),

  adaptResponseData: (response: ImportPreviewResponseWire): ImportPreview | undefined => {
    if (response.status !== 'success' || !response.result) {
      return undefined;
    }

    const { result } = response;

    return {
      groups: result.groups.map((group) => ({
        email: group.email,
        clientName: group.client_name,
        existingClientName: group.existing_client_name ?? null,
        isExisting: group.is_existing ?? false,
        count: group.count ?? 1,
        existingCount: group.existing_count ?? 0,
        newConfigs: group.new_configs ?? 0,
        servers: group.servers ?? [],
        newNames: group.new_names ?? [],
        bindings: group.bindings ?? {},
      })),
      problems: (result.problems ?? []).map((problem) => ({
        line: problem.line,
        raw: problem.raw,
        reason: problem.reason,
      })),
      totalRows: result.total_rows,
      totalRecipients: result.total_recipients,
      totalConfigs: result.total_configs,
    };
  },
};

export default previewRecipientsImportAdapter;
