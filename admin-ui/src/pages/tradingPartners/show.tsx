import { useShow } from "@refinedev/core";
import { Show } from "@refinedev/antd";
import { Descriptions, Card, Tag, Divider } from "antd";
import { IResourceComponentsProps } from "@refinedev/core";

interface ITradingPartner { id: number; name: string; description: string; profiles: IPartnerProfile[]; }
interface IPartnerProfile { id: number; name: string; implementation_guide: string; criteria: IProfileCriterion[]; }
interface IProfileCriterion { id: number; field_source: string; field_identifier: string; operator: string; value: string; }

export const TradingPartnerShow: React.FC<IResourceComponentsProps> = () => {
    const { queryResult } = useShow<ITradingPartner>();
    const { data, isLoading } = queryResult;
    const record = data?.data;

    return (
        <Show isLoading={isLoading}>
            <Descriptions bordered>
                <Descriptions.Item label="ID">{record?.id}</Descriptions.Item>
                <Descriptions.Item label="Name">{record?.name}</Descriptions.Item>
                <Descriptions.Item label="Description">{record?.description}</Descriptions.Item>
            </Descriptions>
            <Divider>Profiles</Divider>
            {record?.profiles?.map(profile => (
                <Card key={profile.id} title={profile.name} style={{ marginBottom: 16 }}>
                    <Descriptions><Descriptions.Item label="Implementation Guide">{profile.implementation_guide}</Descriptions.Item></Descriptions>
                    <Divider orientation="left" plain>Criteria</Divider>
                    {profile.criteria.map(crit => (
                         <Tag key={crit.id} style={{marginBottom: 8}}>{crit.field_source}:{crit.field_identifier} {crit.operator.toLowerCase()} "{crit.value}"</Tag>
                    ))}
                </Card>
            ))}
        </Show>
    );
};