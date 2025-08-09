import { useCustom } from "@refinedev/core";

export interface SftpConfiguration {
  id: number;
  tenant_id: string;
  partner_id: number;
  sftp_enabled: boolean;
  sftp_username: string;
  authentication_type: string;
  tenant_partner_username: string;
  poll_enabled: boolean;
  response_filename_template: string | null;
  response_timeout_minutes: number;
  max_file_size_bytes: number;
  created_at: string;
  updated_at: string | null;
}

export interface CreateSftpConfigurationRequest {
  partner_id: number;
  sftp_enabled?: boolean;
  sftp_username: string;
  authentication_type: string;
  password?: string;
  ssh_public_key?: string;
  file_name_patterns?: string;
  poll_enabled?: boolean;
  response_filename_template?: string;
  response_timeout_minutes?: number;
  max_file_size_bytes?: number;
}

export const useSftpConfiguration = (partnerId?: number) => {
  const { data: sftpConfig, isLoading } = useCustom<SftpConfiguration>({
    url: `/sftp/configurations/${partnerId}`,
    method: "get",
    queryOptions: {
      enabled: !!partnerId,
    },
  });

  const createSftpConfiguration = async (data: CreateSftpConfigurationRequest): Promise<SftpConfiguration> => {
    const response = await fetch("/api/v1/sftp/configurations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${localStorage.getItem("auth_token")}`,
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error("Failed to create SFTP configuration");
    }

    const result = await response.json();
    return result;
  };

  return {
    sftpConfig: sftpConfig?.data,
    isLoading,
    createSftpConfiguration,
  };
};