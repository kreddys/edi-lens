import { Admin, Resource, ListGuesser } from 'react-admin';
import { authProvider } from './authProvider';
import { dataProvider } from './dataProvider';
import { CustomLayout } from './layout';
import { TradingPartnerCreate, TradingPartnerEdit, TradingPartnerList } from './tradingPartners';

export const App = () => (
    <Admin
        dataProvider={dataProvider}
        authProvider={authProvider}
        layout={CustomLayout}
        // No requireAuth prop needed, ra-keycloak handles it
    >
        <Resource
            name="trading-partners"
            list={TradingPartnerList}
            edit={TradingPartnerEdit}
            create={TradingPartnerCreate}
            options={{ label: 'Trading Partners' }}
        />
        <Resource
            name="validate"
            list={ListGuesser}
            options={{ label: 'Validation' }}
        />
    </Admin>
);